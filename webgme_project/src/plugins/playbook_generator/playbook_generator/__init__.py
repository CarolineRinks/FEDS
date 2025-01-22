"""
This is where the implementation of the plugin code goes.
The playbook_generator-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import logging
from webgme_bindings import PluginBase
import os

# Setup a logger
logger = logging.getLogger('playbook_generator')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class playbook_generator(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))

        play_nodes = self.get_objs_of_meta('Play', active_node)
        playbook_data = []

        for play_node in play_nodes:
            play_name = core.get_attribute(play_node, 'name')
            become = core.get_attribute(play_node, 'become') or False
            gather_facts = core.get_attribute(play_node, 'gather_facts') or False

            # Traverse Role nodes under the Play node
            role_nodes = self.get_objs_of_meta('Role', play_node)
            roles = []
            for role_node in role_nodes:
                namespace = core.get_attribute(role_node, 'namespace')
                role_name = core.get_attribute(role_node, 'name')

                if namespace and role_name:
                    roles.append(f"./roles/{namespace}.{role_name}")
                else:
                    logger.warning(f"Role node {core.get_path(role_node)} is missing namespace or name attributes.")

            play = {
                "name": play_name,
                "hosts": "all",  # Default to 'all', can be customized
                "become": become,
                "gather_facts": gather_facts,
                "roles": roles
            }
            playbook_data.append(play)

        # Generate playbook.yml
        self.generate_playbook(playbook_data)

    def get_objs_of_meta(self, meta_name, parent_node):
        """
        Get all child nodes of a specific meta type.

        Args:
            meta_name (str): The name of the meta type to search for.
            parent_node: The parent node to traverse.

        Returns:
            list: A list of matching child nodes.
        """
        children = self.core.load_children(parent_node)
        return [child for child in children if self.core.is_type_of(child, self.META[meta_name])]
    
    def get_experiment_name(self,node):
        """
        Get the experiment name from the active node.

        Returns:
            str: The experiment name.
        """
        ansible_task_node=self.core.get_parent(node)
        # print("ansible_task name: ",self.get_name_of_node(ansible_task_node))
        service_node=self.core.get_parent(ansible_task_node)
        # print("service name: ",self.get_name_of_node(service_node))
        services_node=self.core.get_parent(service_node)
        # print("services name: ",self.get_name_of_node(services_node))
        resources_node=self.core.get_parent(services_node)
        # print("resources name: ",self.get_name_of_node(resources_node))
        experiment_node=self.core.get_parent(resources_node)
        # print("experiment name: ",self.get_name_of_node(experiment_node))

        return self.get_name_of_node(experiment_node)
    
    def get_service_name(self,role_node):
        """
        Get the service name from the active node.

        Returns:
            str: The service name.
        """
        play_node=self.active_node
        # print("play name: ",self.get_name_of_node(play_node))
        playbook_node=self.core.get_parent(play_node)
        # print("playbook name: ",self.get_name_of_node(playbook_node))
        ansible_task_node=self.core.get_parent(playbook_node)
        # print("ansible_task name: ",self.get_name_of_node(ansible_task_node))
        service_node=self.core.get_parent(ansible_task_node)
        # print("service name: ",self.get_name_of_node(service_node))
        return self.get_name_of_node(service_node)
        
    def make_dir(self,roles_dir):
        os.makedirs(roles_dir, exist_ok=True)
                
    def find_path(self,node):
        current_dir = os.getcwd()
        repo_dir = os.path.dirname(current_dir)
        # print("repo_dir -----: ", repo_dir)

        experiment_name = self.get_experiment_name(node)

            # Define the target roles directory
            
        roles_dir = f'{repo_dir}/experiments/{experiment_name}'
        return roles_dir
    
    def get_name_of_node(self,node):
        return self.core.get_attribute(node,'name')
    
    def generate_playbook(self, playbook_data):
        """
        Generate a playbook.yml file based on the collected data.

        Args:
            playbook_data (list): The structured playbook data.
        """
        try:
            roles_dir = self.find_path(self.active_node)
            self.make_dir(roles_dir)
            file_name=self.get_name_of_node(self.active_node)
            output_file = f"{roles_dir}/{file_name}.yml"
            with open(output_file, "w") as file:
                file.write("---\n")
                for play in playbook_data:
                    file.write(f"- name: {play['name']}\n")
                    file.write(f"  hosts: {play['hosts']}\n")
                    file.write(f"  become: {str(play['become']).lower()}\n")
                    file.write(f"  gather_facts: {str(play['gather_facts']).lower()}\n")
                    file.write("  roles:\n")
                    for role in play["roles"]:
                        file.write(f"    - {role}\n")
                    file.write("\n")
            logger.info(f"Playbook generated successfully: {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate playbook: {e}")
