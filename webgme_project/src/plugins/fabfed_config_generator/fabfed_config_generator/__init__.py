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

class LiteralString(str):
    pass

def literal_str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

yaml.add_representer(LiteralString, literal_str_representer)

class fabfed_config_generator(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))

        self.plugin_utils = WebGMEUtils(core, root_node, active_node, self.META)

        self.get_providers_in_the_topology()
        self.generate_config_file()

    def get_provider_of_resource(self, node):
        provider = self.plugin_utils.get_referenced_node(node, 'provider')
        if provider:
            provider_name = self.plugin_utils.core.get_attribute(provider, 'name')
            return provider_name.lower()
        else:
            logger.warning(f'Provider not found for : {node} with name {self.core.get_attribute(node, "name")}')
            return None

    def get_providers_in_the_topology(self):
        provider_set = set()
        networks = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Network')
        nodes = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Node')
        services= self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Service')
        if networks:
            for network in networks:
                provider = self.get_provider_of_resource(network)
                if provider:
                    provider_set.add(provider)
        if services:
            for service in services:
                provider = self.get_provider_of_resource(service)
                if provider:
                    provider_set.add(provider)
        elif nodes:
            for node in nodes:
                provider = self.get_provider_of_resource(node)
                if provider:
                    provider_set.add(provider)

        logger.info('Providers in the topology: {0}'.format(provider_set))
        return list(provider_set)

    def generate_provider_info(self):
        providers_list = self.get_providers_in_the_topology()
        providers_list = [provider.lower() for provider in providers_list]
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
    
    def get_network_of_node(self, node):
        networks= self.plugin_utils.get_dst_of_connections_if_node_is_src('Belongs_To', node)
        if networks:
            if len(networks)==1:
                network = networks[0]
                network_name = self.core.get_attribute(network, 'name')
                logger.info(f'[DEBUG] Network name: {network_name} for the node {self.core.get_attribute(node, "name")}') 
                return network_name, network
            else:
                self.create_message(node, f'More than one network found for the node {self.core.get_attribute(node, "name")}! You should check the model.', 'error')
                raise Exception(f'More than one network found for the node {self.core.get_attribute(node, "name")}! You should check the model.')

        else:
            logger.warning(f'[WARN] No network found for the node {self.core.get_attribute(node, "name")}! Just a warning. Might not be a problem, depending on the provider.')
            self.create_message(node, f'No network found for the node {self.core.get_attribute(node, "name")}! Just a warning. Might not be a problem, depending on the provider.', 'warning')
            return None
                
    #TODO: if the node is attached to a network, the network should be used as a provider, otherwise the provider of the node should be used?

    def _build_node_dict(self, node):
        node_dict = {}
        node_name = self.core.get_attribute(node, 'name')

        # Determine provider and network
        result = self.get_network_of_node(node)
        network_name, network = result if result else (None, None)

        provider = self.get_provider_of_resource(network if network else node)
        if not provider:
            msg = (f"No provider found for the node {node_name}! It is required. "
                f"If the node is attached to a network, the network's provider will be used, "
                f"otherwise the provider of the node should be specified.")
            self.create_message(node, msg, 'error')
            raise Exception(msg)

        provider_var = LiteralString(f"{{{{ {provider}.{provider}_provider }}}}")
        node_dict['provider'] = provider_var

        if network:
            network_var = LiteralString(f"{{{{ network.{network_name} }}}}")
            node_dict['network'] = network_var

        # Include additional node attributes (excluding 'name')
        attr_of_node = self.plugin_utils.get_all_attributes_values(node)
        for _, attr_dict in attr_of_node.items():
            for attr, attr_value in attr_dict.items():
                if attr != 'name' and attr!= 'count' and attr_value:
                    node_dict[attr] = attr_value
                elif attr == 'count':
                    node_dict['count'] = int(attr_value)

        # logger.info(f'[DEBUG] Node attributes for {node_name}: {node_dict}')
        return node_dict
    
    def generate_node_info(self):
        nodes = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Node')
        node_entries = []

        if not nodes:
            return node_entries

        for node in nodes:
            node_dict = self._build_node_dict(node)
            if node_dict:
                node_name = self.core.get_attribute(node, 'name')
                node_entries.append({node_name: node_dict})

        return node_entries
    
    #TODO: is layer3 needed for networks?

    
    def _build_network_dict(self, network, peering_flag):
        network_dict = {}
        network_name = self.core.get_attribute(network, 'name')
        provider = self.get_provider_of_resource(network)
        if not provider:
            msg = (f"No provider found for the network {network_name}! It is required. "
                f"Please check the model.")
            self.create_message(network, msg, 'error')
            raise Exception(msg)
        provider_var = LiteralString(f"{{{{ {provider}.{provider}_provider }}}}")
        network_dict['provider'] = provider_var

        # Include additional network information such as layer and peering (excluding 'name')
        layer3 = self.plugin_utils.get_referenced_node(network, 'layer3')
        if layer3:
            layer3_name = self.core.get_attribute(layer3, 'name')
            logger.info(f'[DEBUG] Layer3 name: {layer3_name} for the network {network_name}')
            layer3_var = LiteralString(f"{{{{ layer3.{layer3_name} }}}}")
            network_dict['layer3'] = layer3_var

        if peering_flag:
            peering_connections = self.plugin_utils.get_connection_info('Peering')
            if peering_connections:
                if provider == 'fabric':
                    # Collect all peering names for the fabric network
                    peering_names = []
                    for src, connection, dst in peering_connections:
                        if src == network or dst == network:
                            peering_name = self.core.get_attribute(connection, 'name')
                            peering_names.append(peering_name)
                    if not peering_names:
                        msg = (f"No peering connection found for the fabric network {network_name}!")
                        self.create_message(network, msg, 'error')
                        raise Exception(msg)
                    # Build a single inline list string (e.g., "['{{ peering.peering1 }}', '{{ peering.peering2 }}']")
                    inline_peering_str = "[" + ", ".join(f"'{{{{ peering.{name} }}}}'" for name in peering_names) + "]"
                    network_dict['peering'] = LiteralString(inline_peering_str)
                elif provider in ['aws', 'gcp']:
                    # For aws and gcp, use the first matching peering
                    found = False
                    for src, connection, dst in peering_connections:
                        if src == network or dst == network:
                            peering_name = self.core.get_attribute(connection, 'name')
                            network_dict['peering'] = LiteralString(f"{{{{ peering.{peering_name} }}}}")
                            found = True
                            break
                    if not found:
                        msg = (f"No peering connection found for the network {network_name}!")
                        self.create_message(network, msg, 'error')
                        raise Exception(msg)
            else:
                msg = (f"No peering connection found for the network {network_name}! It is required for stitching experiments with aws or gcp.")
                self.create_message(network, msg, 'error')
                raise Exception(msg)

        return network_dict

    def generate_network_info(self):
        providers = self.get_providers_in_the_topology()
        peering_flag = False
        if ('aws' in providers or 'gcp' in providers) and ('fabric' in providers):
            peering_flag = True

        networks = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Network')
        logger.info(f'[DEBUG] Networks: {networks}')
        network_entries = []

        if not networks:
            return network_entries

        for network in networks:
            network_dict = self._build_network_dict(network, peering_flag)
            if network_dict:
                network_name = self.core.get_attribute(network, 'name')
                network_entries.append({network_name: network_dict})
                
        return network_entries

    def generate_layer3_info(self):
        layer3s = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Layer_3_Addressing')
        layer3_entries = []
        if not layer3s:
            return layer3_entries
        for layer3 in layer3s:
            layer3_dict = {}
            layer3_name = self.core.get_attribute(layer3, 'name')
            # Include additional layer3 attributes (excluding 'name')
            attr_of_layer3 = self.plugin_utils.get_all_attributes_values(layer3)
            for _, attr_dict in attr_of_layer3.items():
                for attr, attr_value in attr_dict.items():
                    if attr != 'name' and attr_value:
                        layer3_dict[attr] = attr_value
            layer3_entries.append({layer3_name: layer3_dict})
        return layer3_entries
    

    #TODO: some strings are coming in quote for peering and others have no quotes.
    
    def generate_peering_info(self):
        peering_connections = self.plugin_utils.get_connection_info('Peering')
        peering_entries = []
        if not peering_connections:
            return peering_entries
        for src, connection, dst in peering_connections:
            peering_dict = {}
            peering_name = self.core.get_attribute(connection, 'name')
            attr_of_peering = self.plugin_utils.get_all_attributes_values(connection)
            for _, attr_dict in attr_of_peering.items():
                for attr, attr_value in attr_dict.items():
                    if attr != 'name' and attr_value:
                        peering_dict[attr] = attr_value
            peering_entries.append({peering_name: peering_dict})
        return peering_entries
            

    def generate_config_file(self):
        provider_entries = self.generate_provider_info()
        node_entries = self.generate_node_info()
        network_entries = self.generate_network_info()
        layer3_entries = self.generate_layer3_info()
        peering_entries = self.generate_peering_info()
        resources = []
        config=[]

        if network_entries:
            resources.append({'network':network_entries})
        if node_entries:
            resources.append({'node':node_entries})
        logger.info(f"[DEBUG ]resources: {resources}")

        if layer3_entries:
            config.append({'layer3': layer3_entries})
        if peering_entries:
            config.append({'peering': peering_entries})

        config = {
            'provider': provider_entries,
            'resources': resources,
            'config': config,

        }

        output_filename = self.get_current_config().get("file_name")
        if not output_filename:
            output_filename = self.core.get_attribute(self.active_node, "name")

        yaml_content = yaml.dump(
            config,
            default_flow_style=False,
            indent=4,
            sort_keys=False,
            allow_unicode=True
        )

        self.add_file(f"{output_filename}.yaml", yaml_content)
        self.result_set_success(True)
        return config
