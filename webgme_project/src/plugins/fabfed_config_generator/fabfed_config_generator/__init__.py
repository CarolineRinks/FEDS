"""
This is where the implementation of the plugin code goes.
The fabfed_config_generator-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import os
import yaml
import logging
from webgme_bindings import PluginBase
from .utils import WebGMEUtils

# Setup a logger
logger = logging.getLogger('fabfed_config_generator')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class fabfed_config_generator(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))

        self.plugin_utils=WebGMEUtils(core,root_node,active_node,self.META)

        self.get_providers_in_the_topology()
        self.get_provider_of_node()
        self.generate_provider_dict()
        self.generate_config_file()
    
    def get_providers_in_the_topology(self):
        provider_set=set()
        networks=self.plugin_utils.get_nodes_of_meta_type(self.active_node,'Network')
        nodes=self.plugin_utils.get_nodes_of_meta_type(self.active_node,'Node')
        if networks:
            for network in networks:
                provider=self.plugin_utils.get_referenced_node(network,'provider')
                if provider:
                    provider_name=self.plugin_utils.core.get_attribute(provider,'name')
                    provider_set.add(provider_name)
        elif nodes:
            for node in nodes:
                provider=self.plugin_utils.get_referenced_node(node,'provider')
                if provider:
                    provider_name=self.plugin_utils.core.get_attribute(provider,'name')
                    provider_set.add(provider_name)
        
        logger.info('Providers in the topology: {0}'.format(provider_set))
        return list(provider_set)
    
    def generate_provider_dict(self):
        providers_list = self.get_providers()
        providers_list=[provider.lower() for provider in providers_list]
        credential_file = '~/.fabfed/fabfed_credentials.yml'
        
        provider_entries = []
        for provider in providers_list:
            provider_dict = {
                provider: [
                    {
                        f"{provider}_provider": {
                            "credential_file": credential_file,
                            "profile": provider
                        }
                    }
                ]
            }
            provider_entries.append(provider_dict)

        return provider_entries
    
    def get_provider_of_node(self, node):
        provider = self.plugin_utils.get_referenced_node(node, 'provider')
        if provider:
            provider_name = self.plugin_utils.core.get_attribute(provider, 'name')
            return provider_name.lower()
        else:
            logger.warning('Provider not found for node: {0}'.format(node))
            return None

    def generate_config_file(self):
        provider_entries=self.generate_provider_dict()
        

        config={'providers':provider_entries}
        output_filename = self.get_current_config().get("file_name")
        if not output_filename:
            output_filename = self.core.get_attribute(self.active_node, "name")

        yaml_content = yaml.dump(
        config, 
        default_flow_style=False, 
        indent=4, 
        sort_keys=False,  # Ensure proper ordering
        allow_unicode=True  # Ensure proper encoding
    )

        self.add_file(f"{output_filename}.yaml", yaml_content)
        self.result_set_success(True)

        return config




           

           


            



