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
        self.stitching_policies = []
        self.generate_config_file()

    def get_provider_of_resource(self, node):
        provider = self.plugin_utils.get_referenced_node(node, 'provider')
        if provider:
            provider_name = self.plugin_utils.core.get_attribute(provider, 'name')
            if provider_name == 'Chameleon' or provider_name == 'chameleon':
                provider_name = 'chi'
            return provider_name.lower()
        else:
            logger.warning(f'Provider not found for : {node} with name {self.core.get_attribute(node, "name")}')
            return None

    def get_providers_in_the_topology(self):
        provider_set = set()
        networks = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Network')
        nodes = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Node')
        services= self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Services')[0]
        logger.info(f'[DEBUG] Services folder: {self.core.get_attribute(services, "name")}')
        if networks:
            for network in networks:
                provider = self.get_provider_of_resource(network)
                if provider:
                    provider_set.add(provider)
        if services:
            service_nodes = self.plugin_utils.get_nodes_of_meta_type(services, 'Service')
            for service_node in service_nodes:
                logger.info(f'[DEBUG] Service: {self.core.get_attribute(service_node, "name")}')
                provider = self.get_provider_of_resource(service_node)
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
                    node_dict[attr] = attr_value.strip()
                elif attr == 'count':
                    node_dict['count'] = int(attr_value.strip())

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
    


    def generate_stitching_policy(self, fabric_network):
        """
        Generate simple stitching policies for fabric stitched with cloudlab or chameleon.
        This function searches all Stitch_With connections and, for each connection where one
        endpoint is a stitch port belonging to the given fabric network (regardless of whether it
        is the src or dst), it determines the remote network. If its provider is 'cloudlab' or 'chi'
        (Chameleon), then it dynamically builds a policy by extracting attributes from both stitch ports.
        Finally, it updates the remote network's dictionary in network_entries with a stitch_with block
        that references the fabric network and the generated policy.
        """
        policies = []
        fabric_network_name = self.core.get_attribute(fabric_network, 'name')
        logger.info(f"[DEBUG] Starting stitching policy generation for fabric network: {fabric_network_name}")

        # Retrieve all Stitch_With connections.
        stitch_with_conns = self.plugin_utils.get_connection_info('Stitch_With')
        if not stitch_with_conns:
            logger.info("[DEBUG] No Stitch_With connections found. Skipping stitching policy generation.")
            return

        # Get all stitch ports that belong to the fabric network via Belongs_To.
        fabric_stitch_ports = self.plugin_utils.get_src_of_connections_if_node_is_dst('Belongs_To', fabric_network)
        fabric_stitch_ports = [port for port in fabric_stitch_ports if self.core.is_type_of(port, self.META['Stitch_Port'])]
        
                
        logger.info(f"[DEBUG] Found {len(fabric_stitch_ports)} stitch ports associated with fabric network '{fabric_network_name}'.")

        for conn in stitch_with_conns:
            src_node, connection_node, dst_node = conn

            src_name = self.core.get_attribute(src_node, 'name') if src_node else "None"
            dst_name = self.core.get_attribute(dst_node, 'name') if dst_node else "None"
            logger.debug(f"[DEBUG] Processing Stitch_With connection: src='{src_name}', dst='{dst_name}'")

            # Check if either endpoint is one of the fabric stitch ports.
            fabric_in_src = src_node in fabric_stitch_ports
            fabric_in_dst = dst_node in fabric_stitch_ports

            if not (fabric_in_src or fabric_in_dst):
                logger.debug("[DEBUG] Neither endpoint belongs to fabric network. Skipping this connection.")
                continue

            # Identify which node is the fabric stitch port and which is the remote stitch port.
            if fabric_in_src:
                fabric_sp = src_node
                remote_sp = dst_node
            else:
                fabric_sp = dst_node
                remote_sp = src_node

            fabric_sp_name = self.core.get_attribute(fabric_sp, 'name')
            remote_sp_name = self.core.get_attribute(remote_sp, 'name')
            logger.info(f"[DEBUG] Found fabric stitch port '{fabric_sp_name}' connected to remote stitch port '{remote_sp_name}'.")

            # Determine the remote network that the remote stitch port belongs to.
            remote_networks = self.plugin_utils.get_dst_of_connections_if_node_is_src('Belongs_To', remote_sp)
            if not remote_networks:
                logger.warning(f"[WARN] Remote stitch port '{remote_sp_name}' is not connected via Belongs_To to any network. Skipping.")
                continue
            remote_network = remote_networks[0]
            remote_network_name = self.core.get_attribute(remote_network, 'name')
            remote_provider = self.get_provider_of_resource(remote_network)
            logger.info(f"[DEBUG] Remote stitch port '{remote_sp_name}' belongs to network '{remote_network_name}' with provider '{remote_provider}'.")

            
            policy_name = f"{remote_network_name}_{fabric_network_name}"
            policy = {}

            #TODO: if gcp is stitching then peer needs to be gcp and stitch_port needs to be fabric
            policy['producer'] = 'fabric' if remote_provider != 'gcp' else remote_provider
            policy['consumer'] = remote_provider if remote_provider != 'gcp' else 'fabric'

            policy['stitch_port'] = {}
            policy['stitch_port']['peer'] = {}

            if remote_provider == 'gcp':
                # If GCP is stitching, then use the fabric stitch port attributes for the main stitch_port,
                # and use the remote stitch port attributes for the peer, with provider set accordingly.
                for key, value in self.plugin_utils.get_all_attributes_values(fabric_sp).items():
                    for attr, attr_value in value.items():
                        if attr != 'name' and attr_value:
                            policy['stitch_port'][attr] = attr_value
                    policy['stitch_port']['provider'] = 'fabric'
                for key, value in self.plugin_utils.get_all_attributes_values(remote_sp).items():
                    for attr, attr_value in value.items():
                        if attr != 'name' and attr_value:
                            policy['stitch_port']['peer'][attr] = attr_value
                    policy['stitch_port']['peer']['provider'] = 'gcp'
            else:
                # Normal case: use the remote stitch port attributes for stitch_port,
                # and use the fabric stitch port attributes for the peer.
                for key, value in self.plugin_utils.get_all_attributes_values(remote_sp).items():
                    for attr, attr_value in value.items():
                        if attr != 'name' and attr_value:
                            policy['stitch_port'][attr] = attr_value
                    policy['stitch_port']['provider'] = remote_provider
                for key, value in self.plugin_utils.get_all_attributes_values(fabric_sp).items():
                    for attr, attr_value in value.items():
                        if attr != 'name' and attr_value:
                            policy['stitch_port']['peer'][attr] = attr_value
                    policy['stitch_port']['peer']['provider'] = 'fabric'

                self.stitching_policies.append({f'{policy_name}': policy})
                policies.append({f'{remote_network_name}': policy_name})

        return policies

    
    #TODO: is layer3 needed for networks?

    
    def _build_network_dict(self, network, peering_flag):
        network_dict = {}
        network_name = self.core.get_attribute(network, 'name')
        provider = self.get_provider_of_resource(network)

        #checks if the network has a provider
        if not provider:
            msg = (f"No provider found for the network {network_name}! It is required. "
                f"Please check the model.")
            self.create_message(network, msg, 'error')
            raise Exception(msg)
        provider_var = LiteralString(f"{{{{ {provider}.{provider}_provider }}}}")
        network_dict['provider'] = provider_var

        layer3 = self.plugin_utils.get_referenced_node(network, 'layer3')
        if layer3:
            layer3_name = self.core.get_attribute(layer3, 'name')
            logger.info(f'[DEBUG] Layer3 name: {layer3_name} for the network {network_name}')
            layer3_var = LiteralString(f"{{{{ layer3.{layer3_name} }}}}")
            network_dict['layer3'] = layer3_var
        else:
            msg = f"No layer3 found for the network {network_name}! It is required for stitching experiments. Please check the model."
            self.create_message(network, msg, 'warning')
                   

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
            provider= self.get_provider_of_resource(network)
            if provider == 'fabric':
                policies=self.generate_stitching_policy(network)
                if policies:
                    for policy in policies:
                        for key, value in policy.items():
                            if 'stitch_with' not in network_dict:
                                network_dict['stitch_with'] = []

                                stitch_with_dict= {'network': LiteralString(f"{{{{ network.{key} }}}}"), 'stitch_option': {'policy': LiteralString(f"{{{{ policy.{value} }}}}")}}
                                network_dict['stitch_with'].append(stitch_with_dict)
                            else:
                                stitch_with_dict= {'network': LiteralString(f"{{{{ network.{key} }}}}"), 'stitch_option': {'policy': LiteralString(f"{{{{ policy.{value} }}}}")}}
                                network_dict['stitch_with'].append(stitch_with_dict)
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
                        layer3_dict[attr] = attr_value.strip()
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
                        logger.info(f'[DEBUG : generate_peering_info] Peering attribute: {attr} with value {attr_value} and type {type(attr_value)}')
                        peering_dict[attr] = attr_value.strip()
            peering_entries.append({peering_name: peering_dict})
        return peering_entries
    
    def generate_service_info(self):
        services_folder = self.plugin_utils.get_nodes_of_meta_type(self.active_node, 'Services')
        # logger.info(f'[DEBUG] Services: {self.core.get_attribute(services_folder, "name")}')
        service_entries = []
        if not services_folder:
            return service_entries
        
        services_folder = services_folder[0]
        
        services = self.plugin_utils.get_nodes_of_meta_type(services_folder, 'Service')
        for service in services:
            # logger.info(f'[DEBUG] Service: {self.core.get_attribute(service, "name")}')
            service_dict = {}
            service_name = self.core.get_attribute(service, 'name')
            target_hosts_folder = self.plugin_utils.get_nodes_of_meta_type(service, 'Target_Hosts')
            # logger.info(f'[DEBUG] Target hosts folder: {self.core.get_attribute(target_hosts_folder, "name")}')
            if not target_hosts_folder:
                msg = (f"No target host folder found for the service {service_name}! It is required. Please check the model.")
                self.create_message(service, msg, 'error')
                raise Exception(msg)
            
            target_hosts_folder = target_hosts_folder[0]
            target_host_ptrs = self.plugin_utils.get_nodes_of_meta_type(target_hosts_folder, 'Target_Host_Ptr')
            if not target_host_ptrs:
                msg = (f"No target host found for the service {service_name}! It is required. Please check the model.")
                self.create_message(service, msg, 'error')
                raise Exception(msg)
            
            playbook_path = f'Services/{service_name}/main.yaml'
            service_dict['playbook_path'] = playbook_path
            provider = self.get_provider_of_resource(service)
            if not provider:
                msg = (f"No provider found for the service {service_name}! It is required. Please check the model.")
                self.create_message(service, msg, 'error')
                raise Exception(msg)
            
            provider_var = LiteralString(f"{{{{ {provider}.{provider}_provider }}}}")
            service_dict['provider'] = provider_var                  
            target_hosts=[]
            for target_host_ptr in target_host_ptrs:
                target_host = self.plugin_utils.get_referenced_node(target_host_ptr,'node_ptr')
                if target_host:
                    target_host_name = self.core.get_attribute(target_host, 'name')
                    logger.info(f'[DEBUG] Target host name: {target_host_name} for the service {service_name}')
                    target_hosts.append(target_host_name)
                inline_target_hosts_str = "[" + ", ".join(f"'{{{{ node.{target_host_name} }}}}'" for target_host_name in target_hosts) + "]"

            service_dict['node'] = LiteralString(inline_target_hosts_str)            
            service_entries.append({service_name: service_dict})
        return service_entries
            

    def generate_config_file(self):
        provider_entries = self.generate_provider_info()
        node_entries = self.generate_node_info()
        network_entries = self.generate_network_info()
        service_entries = self.generate_service_info()
        layer3_entries = self.generate_layer3_info()
        peering_entries = self.generate_peering_info()

        resources = []
        config=[]

        if network_entries:
            resources.append({'network':network_entries})
        if node_entries:
            resources.append({'node':node_entries})
        if service_entries:
            resources.append({'service':service_entries})
        logger.info(f"[DEBUG ]resources: {resources}")

        if layer3_entries:
            config.append({'layer3': layer3_entries})
        if peering_entries:
            config.append({'peering': peering_entries})

        config = {
            'provider': provider_entries,
            'config': config,
            'resource': resources,
            

        }

        if self.stitching_policies:
            config['config'].append({'policy': self.stitching_policies})


        topology_name = self.core.get_attribute(self.active_node, "name")

        yaml_content = yaml.dump(
            config,
            default_flow_style=False,
            indent=4,
            sort_keys=False,
            allow_unicode=True
        )

        # self.add_file(f"{output_filename}.fab", yaml_content)
        base_dir = f'Experiments/{topology_name}'
        os.makedirs(base_dir, exist_ok=True)
        config_file_path = os.path.join(base_dir, f'config.fab')
        with open(config_file_path, 'w') as file:
            file.write(yaml_content)
        self.create_message(self.active_node, f"Fabfed config file saved at {config_file_path}", 'info')
        self.result_set_success(True)
        return config
