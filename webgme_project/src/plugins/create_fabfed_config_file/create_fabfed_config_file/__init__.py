"""
This is where the implementation of the plugin code goes.
The create_fabfed_config_file-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import logging
from webgme_bindings import PluginBase
import os

# Setup a logger
logger = logging.getLogger('create_fabfed_config_file')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class create_fabfed_config_file(PluginBase):
    def main(self):
        # Setup Node --------------------------------------------------------------
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))

        # -------------------------------------------------------------------

        self.file_string = ''     # The final string that will be written to the fabfed config file. Made up of the strings below
        self.provider_string = ''   # The string for providers
        self.resource_string = ''  # The string for resources
        self.config_string = ''     # The string for config

        self.children = self.core.load_children(self.active_node) 

        fab_filename = self.core.get_attribute(self.active_node, "name")
        print("---------fab_filename: ", fab_filename)
        
        # Get Resources and Config nodes
        _, nodes = self.get_objs_of_meta(self.children, 'Resources')
        self.resources_node = nodes[0]
        _, nodes = self.get_objs_of_meta(self.children, 'Config')
        self.config_node = nodes[0]

        self.providers_list = []    # List to keep track of providers

        # Construct the fabfed config file string
        self.config_generate()
        self.resources_generate()
        self.providers_generate()
        self.file_string += self.provider_string
        self.file_string += self.config_string
        self.file_string += self.resource_string
        #print("------------file_string:--------------\n", self.file_string)

        # Write the entire file
        self.add_file(f"{fab_filename}.fab", str(self.file_string))
        self.result_set_success(True)

    def get_objs_of_meta(self, children, metatype):
        # Helper function to retrieve nodes of given meta type
        names, nodes = [], []
        for child in children:
           if self.core.is_type_of(child, self.META[metatype]): 
               #self.get_all_attributes_values(child)
               #self.get_all_childrens(child)
               nodes.append(child)
               names.append(self.core.get_attribute(child, 'name'))
        return names, nodes 
    
    def network_generate(self, active_node):
        self.networks_string = ''

        # Get all network nodes drag and dropped by the user
        networks = self.core.load_children(active_node) 
        if networks:
            self.networks_string += '  - network:\n'
            for network in networks:
                # Write name of network
                network_name = self.core.get_attribute(network, 'name')
                self.networks_string += '      - ' + network_name + ':\n'

                # Write provider
                provider = self.core.load_pointer(network,'provider')
                if provider:
                    provider_name = self.core.get_attribute(provider, 'name')
                    if provider_name not in self.providers_list:
                        self.providers_list.append(provider_name)    # add provider to keep track of them
                    if provider_name == "Chameleon":
                        self.networks_string += "          provider: '{{ chi.chi_provider }}'\n"
                    else:
                        self.networks_string += "          provider: '{{ " + provider_name.lower() + "." + provider_name.lower() + "_provider }}'\n"
                else:
                    logger.error(f"You must specify a provider for each network!!!!")

                # Write layer3
                layer3 = self.core.load_pointer(network,'layer3')
                if layer3:
                    layer3_name = self.core.get_attribute(layer3, 'name')
                    self.networks_string += "          layer3: '{{ layer3." + layer3_name + " }}'\n"

                # Write each attribute
                attributes = self.core.get_attribute_names(network)
                for attribute in attributes:
                    if attribute == 'layer3' or attribute == 'stitch_with' or attribute == 'stitch_option' or attribute == 'policy':
                        continue
                    value = self.core.get_attribute(network, attribute)
                    if (value) and (attribute != 'name'):
                        self.networks_string += '          ' + attribute + ': ' + str(value) + '\n'

                # Write stitch_with
                stitch_with = self.core.load_pointer(network,'stitch_with')
                if stitch_with:
                    stitch_with_name = self.core.get_attribute(stitch_with, 'name')
                    self.networks_string += "          stitch_with:\n            - network: '{{ network." + stitch_with_name + " }}'\n"

                # Write stitch_option
                stitch_option = self.core.load_pointer(network,'stitch_option')
                if stitch_option:
                    stitch_option_name = self.core.get_attribute(stitch_option, 'name')
                    self.networks_string += "          stitch_option:\n             policy: '{{ policy." + stitch_option_name + " }}'\n"

            self.resource_string += self.networks_string
    
    def service_generate(self, active_node):
        self.services_string = ''

        # Get all service nodes drag and dropped by the user
        services = self.core.load_children(active_node) 
        if services:
            self.services_string += '  - service:\n'
            for service in services:
                # Write name of service
                service_name = self.core.get_attribute(service, 'name')
                self.services_string += '      - ' + service_name + ':\n'

                # Write provider
                # pointer_labels = self.get_pointer_labels(network)
                # print("------------pointer_labels: ", pointer_labels)
                provider = self.core.load_pointer(service,'provider')
                if provider:
                    provider_name = self.core.get_attribute(provider, 'name')
                    if provider_name not in self.providers_list:
                        self.providers_list.append(provider_name)    # add provider to keep track of them
                    if provider_name == "Chameleon":
                        self.services_string += "          provider: '{{ chi.chi_provider }}'\n"
                    else:
                        self.services_string += "          provider: '{{ " + provider_name.lower() + "." + provider_name.lower() + "_provider }}'\n"
                else:
                    logger.error(f"You must specify a provider for each service!!!!")

                # Write nodes attribute
                self.services_string += "          node: ["
                # Get nodes inside of service
                nodes = self.core.load_children(service)
                node_count = 0
                for node in nodes:
                    node_count += 1
                    self.services_string += "'{{ node." + self.core.get_attribute(node, 'name') + " }}', "
                self.services_string = self.services_string[:-2] + "]\n"    # remove the last comma and space and add ending bracket
                
                # Write each attribute
                # attributes = self.core.get_attribute_names(service)
                # for attribute in attributes:
                #     value = self.core.get_attribute(service, attribute)
                #     if (value) and (attribute != 'name'):
                #         self.services_string += '          ' + attribute + ': ' + str(value) + '\n'

                # Write profile
                if provider_name == "Janus":
                    self.services_string += "          profile: fabfed\n"
                elif provider_name == "Chameleon":
                    self.services_string += "          profile: chi\n"
                else:
                    self.services_string += "          profile: " + provider_name.lower() + "\n"

                # Write count of nodes
                self.services_string += "          count: " + str(node_count) + "\n"


            self.resource_string += self.services_string

    def node_generate(self, active_node):
        self.nodes_string = ''

        # Get all nodes
        nodes = self.core.load_children(active_node) 
        if nodes:
            self.nodes_string += '  - node:\n'
            for node in nodes:
                # Write name of node
                node_name = self.core.get_attribute(node, 'name')
                self.nodes_string += '      - ' + node_name + ':\n'

                # Write provider
                #pointer_labels = self.get_pointer_labels(node)
                provider_node = self.core.load_pointer(node,'provider')
                if provider_node:
                    provider_name = self.core.get_attribute(provider_node, 'name')
                    if provider_name not in self.providers_list:
                        self.providers_list.append(provider_name)    # add provider to keep track of them
                    if provider_name == "Chameleon":
                        self.nodes_string += "          provider: '{{ chi.chi_provider }}'\n"
                    else:
                        self.nodes_string += "          provider: '{{ " + provider_name.lower() + "." + provider_name.lower() + "_provider }}'\n"
                else:
                    logger.error(f"You must give each node a provider!!!!")

                # Write network if exists
                network_node = self.core.load_pointer(node,'network')
                if network_node:
                    network_name = self.core.get_attribute(network_node, 'name')
                    self.nodes_string += "          network: '{{ network." + network_name + " }}'\n"

                # Get all attributes of the node
                attributes = self.core.get_attribute_names(node)
                # print("------------attributes:", attributes)

                # Write each attribute
                for attribute in attributes:
                    value = self.core.get_attribute(node, attribute)
                    if (value) and (attribute != 'name'):
                        self.nodes_string += '          ' + attribute + ': ' + str(value) + '\n'


            self.resource_string += self.nodes_string

    def resources_generate(self):

        # Write resources section in file
        self.resource_string += 'resource:\n'
        
        # Get children of Resources node
        children = self.core.load_children(self.resources_node) 
        # Get Networks, Nodes, and Services nodes
        _, networks_node = self.get_objs_of_meta(children, 'Networks')
        _, nodes_node = self.get_objs_of_meta(children, 'Nodes')
        _, services_node = self.get_objs_of_meta(children, 'Services')
        
        # Generate network information
        self.network_generate(networks_node[0])
        # Generate node information
        self.node_generate(nodes_node[0])
        # Generate service information 
        self.service_generate(services_node[0])
        #print("------------resource_string:--------------\n", self.resource_string)
    
    def config_generate(self):

        # Get children of Config node
        children = self.core.load_children(self.config_node) 
        # Get layer3 node and policy node
        _, layer3_node = self.get_objs_of_meta(children, 'Layer3')
        _, policy_node = self.get_objs_of_meta(children, 'Policy')
        if not policy_node and not layer3_node:
            return
        else:
            self.config_string += 'config:\n'
        
        # Generate Policy information
        if policy_node:
            self.policy_generate(policy_node[0])
        # Generate layer3 information
        if layer3_node:
            self.layer3_generate(layer3_node[0])
        #print("------------config_string:--------------\n", self.config_string)

    def policy_generate(self, active_node):
        # Write policy section in file
        self.policy_string = '  - policy:\n'

        # Write name of policy
        self.policy_string += '      - ' + self.core.get_attribute(active_node, 'name') + ':\n'

        # Get all attributes of the policy
        attributes = self.core.get_attribute_names(active_node)
        for attribute in attributes:
            value = self.core.get_attribute(active_node, attribute)
            if (value) and (attribute != 'name'):
                self.policy_string += '          ' + attribute + ': ' + str(value) + '\n'

        # Write stitch_port
        stitch_ports = self.core.load_children(active_node)
        stitch_port = stitch_ports[0] if stitch_ports else None
        if stitch_port:
            self.policy_string += '          stitch_port:\n'
            # Write provider
            provider = self.core.load_pointer(stitch_port, 'provider')
            if provider:
                provider_name = self.core.get_attribute(provider, 'name')
                if provider_name not in self.providers_list:
                    self.providers_list.append(provider_name)   # add provider to keep track of them
                if provider_name == "Chameleon":
                    self.policy_string += "            provider: chi\n"
                else:
                    self.policy_string += "            provider: " + provider_name.lower() + "\n"

            # Get all attributes of the port
            attributes = self.core.get_attribute_names(stitch_port)
            for attribute in attributes:
                value = self.core.get_attribute(stitch_port, attribute)
                if (value):
                    self.policy_string += '            ' + attribute + ': ' + str(value) + '\n'

        # Write Peer
        peers = self.core.load_children(stitch_port)
        peer = peers[0] if peers else None
        if peer:
            self.policy_string += '            peer:\n'
            # Write profile attribute
            profile = self.core.get_attribute(peer, 'profile')
            if profile:
                self.policy_string += '              profile: ' + str(profile) + '\n'
            # Write provider
            provider = self.core.load_pointer(peer, 'provider')
            if provider:
                provider_name = self.core.get_attribute(provider, 'name')
                if provider_name == "Chameleon":
                    self.policy_string += "              provider: chi\n"
                else:
                    self.policy_string += "              provider: " + provider_name.lower() + "\n"
            # Write Cluster
            cluster = self.core.get_attribute(peer, 'cluster')
            if cluster:
                self.policy_string += '              option:\n'
                self.policy_string += '                cluster: ' + str(cluster) + '\n'

        self.config_string += self.policy_string

    def layer3_generate(self, active_node):
        # Write config section in file
        #self.config_string += 'config:\n'

        # Write layer3 section in file
        self.layer3_string = '  - layer3:\n      - ' + self.core.get_attribute(active_node, 'name') + ':\n'

        # Get all attributes of the layer3
        attributes = self.core.get_attribute_names(active_node)
        for attribute in attributes:
            value = self.core.get_attribute(active_node, attribute)
            if (value) and (attribute != 'name'):
                self.layer3_string += '          ' + attribute + ': ' + str(value) + '\n'

        self.config_string += self.layer3_string

    def providers_generate(self):
        
        # Resolve User's home directory
        credentials_path = os.path.expanduser("~/.fabfed/fabfed_credentials.yml")

        # Write providers section in file
        self.provider_string = 'provider:\n'

        #print("--------------------------providers_list: ", self.providers_list)
        for provider in self.providers_list:
            if provider == "Chameleon":
                provider_name = "chi"
            else:
                provider_name = provider.lower()
            self.provider_string += '  - ' + provider_name + ':\n'
            self.provider_string += '      - ' + provider_name + '_provider:\n'
            self.provider_string += '          credential_file: ' + credentials_path + '\n'
            self.provider_string += '          profile: ' + provider_name + '\n'

    def get_pointer_labels(self, node):
        try:
            labels = self.core.get_own_pointer_names(node)
            labels.remove('base')
            print("------------labels: ", labels)
            return labels
        except Exception as e:
            logger.error(f"Error in get_pointer_info: {e}")
            return None
    
    def get_referenced_node_attributes(self, node_ref):
        core = self.core

        # Access the pointer reference from Node_ref
        reference_pointer = core.get_pointer_path(node_ref, 'ref')
        if not reference_pointer:
            self.logger.error("No reference pointer found for the node_ref.")
            return None

        # Load the actual referenced node
        referenced_node = core.load_by_path(self.root_node, reference_pointer)
        if not referenced_node:
            self.logger.error("Failed to load the referenced node.")
            return None

        # Access attributes of the referenced node
        print("referenced node found: ",referenced_node)
        attributes = self.get_all_attributes_values(referenced_node)
        # attributes = {
        #     "aws_info": core.get_attribute(referenced_node, "aws_info"),
        #     "host_type": core.get_attribute(referenced_node, "host_type"),
        #     "type": core.get_attribute(referenced_node, "type"),
        # }

        # Log the attributes for debugging
        self.logger.info(f"Attributes of the referenced node: {attributes}")

        return referenced_node


