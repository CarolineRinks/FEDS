import sys
import logging
import subprocess
from webgme_bindings import PluginBase
import os
import shutil
# Setup a logger
logger = logging.getLogger('install_role')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class install_role(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        children=self.load_all_children(active_node)
        print("children: ",children)
        role_nodes=self.get_objs_of_meta('Role',children)
        print("role_nodes: ",role_nodes)

        if not role_nodes:
            logger.error("No role nodes found under the active node.")

        # Fetch role info
        self.fetch_role_info(role_nodes)


    def not_role_name(self,role_node):
        logger.error("Role name is missing for role node '{0}'.".format(self.get_name_of_node(role_node)))

    def not_role_namespace(self,role_node,role_name):

        logger.warning("Namespace is missing for role node '{0}'.".format(self.get_name_of_node(role_node)))
        search_results = self.search_role(role_name)
        if search_results:
            logger.info("Search results:\n{0}".format(search_results))
            logger.warning("----- Please select a namespace and appropriate role name and update the model in WebGME. -----")
        else:
            logger.error("No results found for role '{0}'.".format(role_name))


    def fetch_role_info(self, role_nodes):
        """
        Fetch namespace and role name from the active node.

        Returns:
            tuple: (namespace, role_name)
        """
        roles=[]
        for role_node in role_nodes:
            namespace = self.core.get_attribute(role_node, 'namespace')
            role_name = self.core.get_attribute(role_node, 'name')
            if not role_name:
                self.not_role_name(role_node)
            if not namespace:
                self.not_role_namespace(role_node,role_name)
            # if namespace and role_name:
            #     self.move_role(role_name, namespace,role_node)
            if namespace and role_name:
                self.install_role(namespace, role_name,role_node)
                self.move_role(role_name, namespace,role_node)
                # print("namespace and role_name: ",namespace,role_name)
                # roles.append((namespace, role_name))
        # print("--------roles--------", roles)

    def get_experiment_name(self,role_node):
        """
        Get the experiment name from the active node.

        Returns:
            str: The experiment name.
        """
        play_node=self.active_node
        # print("play name: ",self.get_name_of_node(play_node))
        playbook_node=self.core.get_parent(play_node)
        # print("playbook name: ",self.get_name_of_node(playbook_node))
        ansible_task_node=self.core.get_parent(playbook_node)
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
                
    def find_path(self,role_node):
        current_dir = os.getcwd()
        repo_dir = os.path.dirname(current_dir)
        # print("repo_dir -----: ", repo_dir)
        service_name = self.get_service_name(role_node)
        experiment_name = self.get_experiment_name(role_node)

            # Define the target roles directory
            
        roles_dir = f'{repo_dir}/experiments/{experiment_name}/{service_name}/roles'
        return roles_dir
    


    def move_role(self, role_name, namespace, role_node):
        try:
            roles_dir = self.find_path(role_node)
            self.make_dir(roles_dir)

            # Define the source and target paths for the role
            ansible_roles_path = os.path.expanduser(f'~/.ansible/roles')
            role_source_path = f'{ansible_roles_path}/{namespace}.{role_name}'  # Corrected the source path
            print("role_source_path: ", role_source_path)
            role_target_path = f'{roles_dir}'
            print("role_target_path: ", role_target_path)

            # Check if the role exists in the source directory
            if os.path.exists(role_source_path):
                print("-----IN HERE-----")
                # Move the role to the target directory
                shutil.move(role_source_path, role_target_path)
                logger.info(f"Role '{namespace}.{role_name}' moved to '{role_target_path}'.")
            else:
                logger.error(f"Role '{namespace}.{role_name}' not found in '{ansible_roles_path}'.")
        except Exception as e:
            logger.error(f'Failed to move role directory: {e}')


    def search_role(self, role_name):
        """
        Search for roles using ansible-galaxy search.

        Args:
            role_name (str): The name of the role to search for.

        Returns:
            str: Formatted search results or None if no results found.
        """
        try:
            command = ["ansible-galaxy", "search", role_name]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error("Error during search: {0}".format(result.stderr.strip()))
        except Exception as e:
            logger.error("An error occurred while searching for the role: {0}".format(e))
        return None

    def install_role(self, namespace, role_name,role_node):
        """
        Install a role using ansible-galaxy install.

        Args:
            namespace (str): The namespace of the role.
            role_name (str): The name of the role.

        Returns:
            bool: True if the installation succeeded, False otherwise.
        """
        try:
            role_identifier = "{0}.{1}".format(namespace, role_name)
            command = ["ansible-galaxy", "install", role_identifier]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                logger.info("Installation output:\n{0}".format(result.stdout.strip()))
                return True
            else:
                logger.error("Installation error: {0}".format(result.stderr.strip()))
        except Exception as e:
            logger.error("An error occurred while installing the role: {0}".format(e))
        return False
    
    def load_all_children(self,node):
        children=[]
        for child in self.core.load_children(node):
            children.append(child)
            # print("child: ",self.core.get_attribute(child, 'name') )
        return children
    
    def get_objs_of_meta(self,metatype,children):
        #return names of node and node objects of given meta type
        _nodes_=[]
        for child in children :
           if self.core.is_type_of(child,self.META[metatype]): 
               _nodes_.append(child)

        return _nodes_
    def get_name_of_node(self,node):
        return self.core.get_attribute(node,'name') 