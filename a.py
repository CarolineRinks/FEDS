import requests

def get_roles_count():
    url = "https://galaxy.ansible.com/api/v2/roles/?page=1&page_size=100"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        roles = data['results']
        print(f"Number of roles in this page: {len(roles)}")
        total_roles = data['count']
        print(f"Total number of roles: {total_roles}")
    else:
        print("Failed to retrieve data")

# Example usage
get_roles_count()
