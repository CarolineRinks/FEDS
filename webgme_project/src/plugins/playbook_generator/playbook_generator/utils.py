import logging

# Setup a logger
logger = logging.getLogger('webgme_util')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class WebGMEUtils:
    def __init__(self, core, root_node, active_node, meta):
        self.core = core
        self.root_node = root_node
        self.active_node = active_node
        self.META = meta

    def get_all_attributes_values(self, node):
        """Returns a dictionary of attribute names and values for a given node."""
        attributes = self.core.get_attribute_names(node)
        return {self.core.get_attribute(node, 'name'): {attr: self.core.get_attribute(node, attr) for attr in attributes}}

    def get_nodes_of_meta_type(self, node, meta_type):
        """Fetches all children nodes of node (for example, active_node) of the given meta type."""
        all_children = self.load_all_immediate_children(node)
        return [child for child in all_children if self.core.is_type_of(child, self.META[meta_type])]

    def load_all_immediate_children(self, node):
        """Loads all children of a given node."""
        return self.core.load_children(node)

    def get_referenced_node(self, node, ptr_name):
        """Retrieves the node referenced by a given pointer."""
        reference_pointer = self.core.get_pointer_path(node, ptr_name)
        if not reference_pointer:
            # logger.error(f"No reference pointer found for {ptr_name}.")
            return None
        return self.core.load_by_path(self.root_node, reference_pointer)

    def get_all_connections_where_node_is_src(self, meta_type_of_connection, src_node):
        """Checks if a node is the source of a given connection meta type and returns the connection."""
        src_connection_dst = self.get_connection_info(meta_type_of_connection)
        if not src_connection_dst:
            logger.info(f" [WARN] No source node for connection of Meta-Type {meta_type_of_connection} found!")
        return [connection for src, connection, _ in src_connection_dst if src == src_node]
    
    def get_all_connections_where_node_is_dst(self, meta_type_of_connection, dst_node):
        """Checks if a node is the source of a given connection meta type and returns the connection."""
        src_connection_dst = self.get_connection_info(meta_type_of_connection)
        if not src_connection_dst:
            logger.info(f" [WARN] No source node for connection of Meta-Type {meta_type_of_connection} found!")
        return [connection for _, connection, dst in src_connection_dst if dst == dst_node]
    
    def get_dst_of_connection(self, connection):
        """Returns the destination of a connection."""
        return self.core.load_pointer(connection, 'dst')
    
    def get_src_of_connection(self, connection):
        """Returns the destination of a connection."""
        return self.core.load_pointer(connection, 'src')
    
    def get_dst_of_connections_if_node_is_src(self,meta_type_of_connection, src_node):
        """Returns the destination of a connection if a node is the source of a given connection meta type."""
        dst=[]
        src_connection_dst = self.get_connection_info(meta_type_of_connection)
        dst = [dst for src, _, dst in src_connection_dst if src == src_node]
        return dst
    
    def get_src_of_connections_if_node_is_dst(self,meta_type_of_connection, dst_node):
        """Returns the source of a connection if a node is the destination of a given connection meta type."""
        src=[]
        src_connection_dst = self.get_connection_info(meta_type_of_connection)
        src = [src for src, _, dst in src_connection_dst if dst == dst_node]
        return src
    
    def get_all_connections_with_given_src_and_dst(self, meta_type_of_connection, src_node, dst_node):
        """Checks if node A is the source and node B is the destination of a given connection meta type and returns the connection."""
        src_connection_dst = self.get_connection_info(meta_type_of_connection)
        return [connection for src, connection, dst in src_connection_dst if src == src_node and dst == dst_node]


    def get_connection_info(self, meta_type_of_connection):
        """Retrieves all source-connection-destination relationships for a given meta type."""
        # try:
        connection_nodes = self.get_nodes_of_meta_type(self.active_node, meta_type_of_connection)
        
        src_connection_dst = []
        for connection_node in connection_nodes:
            src = self.core.load_pointer(connection_node, 'src')
            dst = self.core.load_pointer(connection_node, 'dst')
            src_connection_dst.append([src, connection_node, dst])
        
        if not src_connection_dst:
            logger.info(f" [WARN] No connection of Meta-Type {meta_type_of_connection} found!")
        return src_connection_dst
        

    def testing(self):
        return "Hello, World!"