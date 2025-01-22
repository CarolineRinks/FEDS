"""
This is where the implementation of the plugin code goes.
The apply-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import logging
from webgme_bindings import PluginBase
import os

# Setup a logger
logger = logging.getLogger('apply')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class apply(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))
    


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
