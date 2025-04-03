"""
This is where the implementation of the plugin code goes.
The playbook_generator-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import logging
from webgme_bindings import PluginBase
import os
import yaml
from .utils import WebGMEUtils

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

        self.plugin_utils = WebGMEUtils(core, root_node, active_node, self.META)

        tasks_nodes = self.plugin_utils.get_nodes_of_meta_type(active_node, 'Tasks')
        if not tasks_nodes:
            msg= f" No Tasks Node found. It is required if you want to generate a playbook."
            self.create_message(active_node,msg,'error')
            raise Exception(msg)
        
        # Traverse Task nodes
        for tasks_node in tasks_nodes:
            task_name= core.get_attribute(tasks_node, 'name')
            logger.info(f"Task node name: {task_name}")
            self.generate_playbook_for_tasks(tasks_node)
        self.generate_main_playbook()
        
        

        # play_nodes = self.get_objs_of_meta('Play', active_node)
        # playbook_data = []

        # for play_node in play_nodes:
        #     play_name = core.get_attribute(play_node, 'name')
        #     become = core.get_attribute(play_node, 'become') or False
        #     gather_facts = core.get_attribute(play_node, 'gather_facts') or False

        #     # Traverse Role nodes under the Play node
        #     role_nodes = self.get_objs_of_meta('Role', play_node)
        #     roles = []
        #     for role_node in role_nodes:
        #         namespace = core.get_attribute(role_node, 'namespace')
        #         role_name = core.get_attribute(role_node, 'name')

        #         if namespace and role_name:
        #             roles.append(f"./roles/{namespace}.{role_name}")
        #         else:
        #             logger.warning(f"Role node {core.get_path(role_node)} is missing namespace or name attributes.")

        #     play = {
        #         "name": play_name,
        #         "hosts": "all",  # Default to 'all', can be customized
        #         "become": become,
        #         "gather_facts": gather_facts,
        #         "roles": roles
        #     }
        #     playbook_data.append(play)

        # # Generate playbook.yml
        # self.generate_playbook(playbook_data)

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
        service_node=self.core.get_parent(node)
        # print("ansible_task name: ",self.get_name_of_node(ansible_task_node))
        services_node=self.core.get_parent(service_node)
        # print("resources name: ",self.get_name_of_node(resources_node))
        experiment_node=self.core.get_parent(service_node)
        # print("experiment name: ",self.get_name_of_node(experiment_node))

        return self.core.get_attribute(experiment_node,'name')
    
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
    
    def generate_playbook_for_tasks(self, tasks_node):
        """
        Generate a playbook YAML file based on roles under the given tasks_node.

        Args:
            tasks_node: The node representing the tasks.
        """

        try:
            # Determine output filename from task node attributes
            order_of_execution = self.core.get_attribute(tasks_node, 'order_of_execution')
            output_filename = f"{self.core.get_attribute(tasks_node, 'name')}"

            # Get roles under this task node
            role_nodes = self.plugin_utils.get_nodes_of_meta_type(tasks_node, 'Role')
            if not role_nodes:
                msg = "No Role node found. At least one role is required to generate a playbook."
                self.create_message(tasks_node, msg, 'error')
                raise Exception(msg)

            # Collect and sort roles by their order_of_execution
            roles = []
            for role_node in role_nodes:
                role_name = self.get_name_of_node(role_node)
                role_namespace = self.core.get_attribute(role_node, 'namespace')
                role_order = self.core.get_attribute(role_node, 'order_of_execution') or 0
                role_id = f"{role_namespace}.{role_name}" if role_namespace else role_name
                roles.append((role_order, {"role": role_id}))

            # Sort roles by order_of_execution
            roles_sorted = [r[1] for r in sorted(roles, key=lambda x: x[0])]


            # Construct the play
            play = {
                "name": self.core.get_attribute(tasks_node, 'name') or f"Play {order_of_execution}",
                "hosts": "all",
                "become": True,
                "gather_facts": True,
                "roles": roles_sorted
            }

            playbook = [play]
            logger.info(f"Playbook data: {playbook}")

            # Serialize playbook to YAML
            yaml_content = yaml.dump(
                playbook,
                default_flow_style=False,
                indent=4,
                sort_keys=False,
                allow_unicode=True
            )
            topology_name = self.get_experiment_name(self.active_node)
            service_name = self.core.get_attribute(self.active_node, 'name')
            logger.info(f" [DEBUG] --------- Service name: {service_name}")
            logger.info(f" [DEBUG] --------- Topology name: {topology_name}")
            # Add the file to WebGME
            base_dir = f'Experiments/{topology_name}/Services/{service_name}'
            os.makedirs(base_dir, exist_ok=True)
            config_file_path = os.path.join(base_dir, f'{output_filename}.yaml')
            with open(config_file_path, 'w') as file:
                file.write(yaml_content)
            self.create_message(self.active_node, f"Playbook {output_filename}.yaml saved to {config_file_path}", 'info')
            self.result_set_success(True)
            return playbook

        except Exception as e:
            logger.error(f"Failed to generate playbook: {e}")
            self.result_set_success(False)
            return None

    def generate_main_playbook(self):
        """
        Generates a main playbook that imports task playbooks in order of execution.
        """
        try:
            # Collect and sort all task nodes by order_of_execution
            tasks_nodes = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Tasks')
            if not tasks_nodes:
                msg = "No Tasks node found. Cannot generate main playbook."
                self.create_message(self.active_node, msg, 'error')
                raise Exception(msg)

            # Sort tasks nodes
            tasks_sorted = sorted(
                tasks_nodes,
                key=lambda n: self.core.get_attribute(n, 'order_of_execution') or 0
            )

            # Generate list of playbook includes
            main_playbook = []
            for tasks_node in tasks_sorted:
                playbook_name = f"{self.core.get_attribute(tasks_node, 'name')}.yaml"
                main_playbook.append({'import_playbook': playbook_name})

            # Write the main playbook
            yaml_content = yaml.dump(
                main_playbook,
                default_flow_style=False,
                indent=4,
                sort_keys=False,
                allow_unicode=True
            )

            # top_playbook_name = f"{self.core.get_attribute(self.active_node, 'name') or 'main'}.yaml"
            topology_name = self.get_experiment_name(self.active_node)
            service_name = self.core.get_attribute(self.active_node, 'name')
            logger.info(f" [DEBUG] --------- Service name: {service_name}")
            logger.info(f" [DEBUG] --------- Topology name: {topology_name}")
            # Add the file to WebGME
            base_dir = f'Experiments/{topology_name}/Services/{service_name}'
            os.makedirs(base_dir, exist_ok=True)
            config_file_path = os.path.join(base_dir, 'main.yaml')
            with open(config_file_path, 'w') as file:
                file.write(yaml_content)
            self.create_message(self.active_node, f"Playbook main.yaml saved to {config_file_path}", 'info')
            self.result_set_success(True)
            return main_playbook

        except Exception as e:
            logger.error(f"Failed to generate main playbook: {e}")
            self.result_set_success(False)


        
