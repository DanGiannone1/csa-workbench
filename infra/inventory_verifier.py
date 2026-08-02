"""Validate a deployed Azure inventory from a file.

Keeping the large policy in a file avoids Windows command-line and environment
limits while preserving the existing fail-closed checks.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
os.environ.update(payload)
import json, os
apps = json.loads(os.environ['APPS']); deployments = json.loads(os.environ['DEPLOYMENTS']); identities = json.loads(os.environ['IDENTITIES'])
import uuid
resources = json.loads(os.environ['RESOURCES']); acr = json.loads(os.environ['ACR']); aoai = json.loads(os.environ['AZURE_OPEN_AI'])
foundry_project = json.loads(os.environ['FOUNDRY_PROJECT'])
system_topics = json.loads(os.environ['SYSTEM_TOPICS']); system_topic_subscriptions = json.loads(os.environ['SYSTEM_TOPIC_SUBSCRIPTIONS'])
cosmos = json.loads(os.environ['COSMOS']); storage = json.loads(os.environ['STORAGE']); vnet = json.loads(os.environ['VNET'])
private_endpoints = json.loads(os.environ['PRIVATE_ENDPOINTS']); zones = json.loads(os.environ['PRIVATE_DNS_ZONES']); environment = json.loads(os.environ['MANAGED_ENVIRONMENT'])
network_security_groups = json.loads(os.environ['NETWORK_SECURITY_GROUPS'])
cosmos_links = json.loads(os.environ['COSMOS_DNS_LINKS']); storage_links = json.loads(os.environ['STORAGE_DNS_LINKS'])
openai_links = json.loads(os.environ['OPENAI_DNS_LINKS']); cognitive_services_links = json.loads(os.environ['COGNITIVE_SERVICES_DNS_LINKS']); ai_services_links = json.loads(os.environ['AI_SERVICES_DNS_LINKS'])
cosmos_groups = json.loads(os.environ['COSMOS_DNS_GROUPS']); storage_groups = json.loads(os.environ['STORAGE_DNS_GROUPS']); openai_groups = json.loads(os.environ['OPENAI_DNS_GROUPS'])
cosmos_records = json.loads(os.environ['COSMOS_DNS_RECORDS']); storage_records = json.loads(os.environ['STORAGE_DNS_RECORDS'])
openai_records = json.loads(os.environ['OPENAI_DNS_RECORDS']); cognitive_services_records = json.loads(os.environ['COGNITIVE_SERVICES_DNS_RECORDS']); ai_services_records = json.loads(os.environ['AI_SERVICES_DNS_RECORDS'])
assignments = [item for group in json.loads(os.environ['ASSIGNMENTS']) for item in group]
cosmos_assignments = json.loads(os.environ['COSMOS_SQL_ASSIGNMENTS'])
app_insights = json.loads(os.environ['APP_INSIGHTS']); log_analytics = json.loads(os.environ['LOG_ANALYTICS'])
app_insights_connection = app_insights.get('properties', {}).get('ConnectionString')
expected_apps = {os.environ['FRONTEND_APP_NAME']: (True, 3000, 'csa-workbench-frontend'), os.environ['API_APP_NAME']: (True, 8000, 'csa-workbench-api'), os.environ['RUNTIME_APP_NAME']: (False, 8080, 'csa-workbench-runtime')}
app_names = [app.get('name') for app in apps] if isinstance(apps, list) and all(isinstance(app, dict) for app in apps) else []
if len(app_names) != len(expected_apps) or len(app_names) != len(set(app_names)) or set(app_names) != set(expected_apps): raise SystemExit('Container App inventory drifted')
expected_identities = {os.environ['FRONTEND_IDENTITY_NAME'], os.environ['API_IDENTITY_NAME'], os.environ['RUNTIME_IDENTITY_NAME']}
identity_names = [identity.get('name') for identity in identities] if isinstance(identities, list) and all(isinstance(identity, dict) for identity in identities) else []
if len(identity_names) != len(expected_identities) or len(identity_names) != len(set(identity_names)) or set(identity_names) != expected_identities: raise SystemExit('managed identity inventory drifted')
def strict_env(container, profile):
    entries = container.get('env', [])
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise SystemExit(f'{profile} environment profile drifted')
    names = [entry.get('name') for entry in entries]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise SystemExit(f'{profile} environment profile drifted')
    return {entry['name']: entry.get('value') for entry in entries}
for app in apps:
    external, port, repository = expected_apps[app['name']]; p = app.get('properties', {}); template = p.get('template', {}); containers = template.get('containers', [])
    ingress = p.get('configuration', {}).get('ingress', {})
    expected_identity = {'csa-workbench-frontend': os.environ['FRONTEND_IDENTITY_NAME'], 'csa-workbench-api': os.environ['API_IDENTITY_NAME'], 'csa-workbench-runtime': os.environ['RUNTIME_IDENTITY_NAME']}[repository]
    expected_identity_id = next(identity.get('id') for identity in identities if identity.get('name') == expected_identity)
    scale = template.get('scale', {})
    scale_valid = (
        isinstance(scale, dict)
        and set(scale) <= {'minReplicas', 'maxReplicas', 'cooldownPeriod', 'pollingInterval', 'rules'}
        and type(scale.get('minReplicas')) is int and scale.get('minReplicas') == 0
        and type(scale.get('maxReplicas')) is int and scale.get('maxReplicas') == 1
        and scale.get('cooldownPeriod') in (None, 300)
        and scale.get('pollingInterval') in (None, 30)
        and scale.get('rules') is None
    )
    registries = p.get('configuration', {}).get('registries')
    registry_valid = isinstance(registries, list) and len(registries) == 1 and isinstance(registries[0], dict)
    if registry_valid:
        registry = registries[0]
        registry_valid = (
            set(registry) <= {'server', 'identity', 'username', 'passwordSecretRef'}
            and registry.get('server') == f'{os.environ["ACR_NAME"]}.azurecr.io'
            and registry.get('identity', '').lower() == expected_identity_id.lower()
            and registry.get('username') in (None, '')
            and registry.get('passwordSecretRef') in (None, '')
        )
    identity_assignments = app.get('identity', {}).get('userAssignedIdentities')
    assigned_identities = {identity_id.lower() for identity_id in identity_assignments} if isinstance(identity_assignments, dict) and all(isinstance(identity_id, str) for identity_id in identity_assignments) else set()
    expected_main_name = {'csa-workbench-frontend': 'frontend', 'csa-workbench-api': 'api', 'csa-workbench-runtime': 'runtime'}[repository]
    expected_container_names = {expected_main_name}
    if repository == 'csa-workbench-runtime' or (repository == 'csa-workbench-api' and os.environ['IDENTITY_MODE'] == 'entra'):
        expected_container_names.add('mise-auth')
    if not isinstance(containers, list) or any(not isinstance(container, dict) for container in containers):
        raise SystemExit('Container App identity, registry, or profile drifted')
    container_names = [container.get('name') for container in containers]
    if any(not isinstance(name, str) or not name for name in container_names) or len(container_names) != len(set(container_names)) or set(container_names) != expected_container_names:
        raise SystemExit('Container App identity, registry, or profile drifted')
    containers_by_name = {container['name']: container for container in containers}
    main = containers_by_name.get(expected_main_name, {})
    if p.get('provisioningState') != 'Succeeded' or p.get('workloadProfileName') != 'Consumption' or ingress.get('external') is not external or ingress.get('targetPort') != port or ingress.get('transport', '').lower() != 'auto' or not scale_valid or set(containers_by_name) != expected_container_names or main.get('image', '').split('/')[-1] != f'{repository}:{os.environ["SHA"]}' or not isinstance(identity_assignments, dict) or assigned_identities != {expected_identity_id.lower()} or not registry_valid: raise SystemExit('Container App identity, registry, or profile drifted')
    main_env = strict_env(main, f'{expected_main_name} container')
    main_env_entries = {entry['name']: entry for entry in main.get('env', [])}
    if repository in ('csa-workbench-api', 'csa-workbench-runtime') and main_env.get('APPLICATIONINSIGHTS_CONNECTION_STRING') != app_insights_connection:
        raise SystemExit('Application Insights trace binding drifted')
    if repository == 'csa-workbench-api':
        expected_api_auth = {
            'IDENTITY_MODE': os.environ['IDENTITY_MODE'], 'ENTRA_TENANT_ID': os.environ['TENANT_ID'],
            'ENTRA_API_CLIENT_ID': os.environ['API_CLIENT_ID'], 'ENTRA_ALLOWED_AUDIENCES': f'api://{os.environ["API_CLIENT_ID"]}',
            'POOL_AUTH_AUDIENCE': f'api://{os.environ["RUNTIME_CLIENT_ID"]}',
        }
        if any(main_env.get(name) != value for name, value in expected_api_auth.items()):
            raise SystemExit('API identity binding drifted')
        demo_password = main_env_entries.get('DEMO_PASSWORD', {})
        if os.environ['IDENTITY_MODE'] == 'demo':
            if main_env.get('MISE_VALIDATION_ENDPOINT') is not None or demo_password.get('secretRef') != 'demo-password' or demo_password.get('value') not in (None, ''):
                raise SystemExit('demo API identity binding drifted')
        elif 'DEMO_PASSWORD' in main_env_entries:
            raise SystemExit('Entra API identity binding drifted')
    if repository == 'csa-workbench-runtime':
        expected_runtime_auth = {
            'WORKLOAD_AUTH_MODE': 'entra', 'WORKLOAD_ENTRA_TENANT_ID': os.environ['TENANT_ID'],
            'WORKLOAD_ENTRA_AUDIENCE': os.environ['RUNTIME_CLIENT_ID'],
            'WORKLOAD_ENTRA_CALLER_OBJECT_ID': os.environ['API_PRINCIPAL'],
            'WORKLOAD_ENTRA_REQUIRED_ROLE': 'invoke',
        }
        if any(main_env.get(name) != value for name, value in expected_runtime_auth.items()):
            raise SystemExit('runtime workload identity binding drifted')
    if 'mise-auth' in expected_container_names:
        sidecar = containers_by_name['mise-auth']
        sidecar_env = strict_env(sidecar, 'Microsoft identity sidecar')
        sidecar_client_id = os.environ['API_CLIENT_ID'] if repository == 'csa-workbench-api' else os.environ['RUNTIME_CLIENT_ID']
        expected_sidecar_env = {
            'Kestrel__Endpoints__Http__Url': 'http://127.0.0.1:8081', 'ASPNETCORE_ENVIRONMENT': 'Production',
            'AzureAd__Instance': 'https://login.microsoftonline.com/', 'AzureAd__TenantId': os.environ['TENANT_ID'],
            'AzureAd__ClientId': sidecar_client_id, 'AzureAd__Audience': sidecar_client_id,
            'Logging__LogLevel__Default': 'Warning', 'Logging__LogLevel__Microsoft.Identity.Web': 'Information',
        }
        expected_sidecar_env['AzureAd__Scopes' if repository == 'csa-workbench-api' else 'AzureAd__Roles'] = 'access_as_user' if repository == 'csa-workbench-api' else 'invoke'
        expected_sidecar_resources = {'cpu': 0.25, 'memory': '0.5Gi', 'ephemeralStorage': '1Gi'}
        if sidecar.get('image') != os.environ['MISE_SIDECAR_IMAGE'] or sidecar.get('resources') != expected_sidecar_resources or sidecar_env != expected_sidecar_env or main_env.get('MISE_VALIDATION_ENDPOINT') != 'http://127.0.0.1:8081/Validate': raise SystemExit('Microsoft identity sidecar profile drifted')
    elif 'MISE_VALIDATION_ENDPOINT' in main_env:
        raise SystemExit('demo API unexpectedly enables Microsoft identity validation')
    if app['name'] == os.environ['RUNTIME_APP_NAME']:
        endpoint = aoai.get('properties', {}).get('endpoint')
        if main_env.get('AZURE_DEPLOYMENT') != os.environ['MODEL_DEPLOYMENT_NAME'] or main_env.get('AZURE_ENDPOINT') != f'{endpoint.rstrip("/")}/openai/v1/': raise SystemExit('runtime Azure OpenAI binding drifted')
expected_deployment_profiles = {
    os.environ['MODEL_DEPLOYMENT_NAME']: (os.environ['MODEL_NAME'], os.environ['MODEL_VERSION'], os.environ['MODEL_SKU_NAME'], int(os.environ['MODEL_CAPACITY'])),
    os.environ['LEGACY_MODEL_DEPLOYMENT_NAME']: (os.environ['LEGACY_MODEL_NAME'], os.environ['LEGACY_MODEL_VERSION'], os.environ['LEGACY_MODEL_SKU_NAME'], int(os.environ['LEGACY_MODEL_CAPACITY'])),
}
if not isinstance(deployments, list) or {d.get('name') for d in deployments} != set(expected_deployment_profiles) or len(deployments) != len(expected_deployment_profiles): raise SystemExit('Azure OpenAI deployment inventory drifted')
for d in deployments:
    model = d.get('properties', {}).get('model', {})
    name, version, sku_name, capacity = expected_deployment_profiles[d['name']]
    if d.get('properties', {}).get('provisioningState') != 'Succeeded' or model.get('format') != 'OpenAI' or d.get('sku', {}).get('name') != sku_name or d.get('sku', {}).get('capacity') != capacity or model.get('name') != name or model.get('version') != version: raise SystemExit('Azure OpenAI model profile drifted')
if acr.get('name') != os.environ['ACR_NAME'] or acr.get('sku', {}).get('name') != 'Basic' or acr.get('adminUserEnabled') is not False: raise SystemExit('Container Registry profile drifted')
if aoai.get('name') != os.environ['AOAI_NAME'] or aoai.get('kind') != 'AIServices' or aoai.get('sku', {}).get('name') != 'S0' or aoai.get('properties', {}).get('disableLocalAuth') is not True or aoai.get('properties', {}).get('allowProjectManagement') is not True or aoai.get('properties', {}).get('publicNetworkAccess') != 'Disabled': raise SystemExit('Azure OpenAI account profile drifted')
if foundry_project.get('name') != f"{os.environ['AOAI_NAME']}/{os.environ['FOUNDRY_PROJECT_NAME']}" or foundry_project.get('properties', {}).get('provisioningState') != 'Succeeded': raise SystemExit('Foundry project profile drifted')
if cosmos.get('disableLocalAuth') is not True or cosmos.get('publicNetworkAccess') != 'Disabled' or cosmos.get('enableAutomaticFailover') is not True: raise SystemExit('Cosmos authentication/network/failover profile drifted')
if storage.get('publicNetworkAccess') != 'Disabled' or storage.get('allowSharedKeyAccess') is not False or storage.get('allowBlobPublicAccess') is not False: raise SystemExit('Storage authentication/public-blob profile drifted')
expected_workspace_id = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.OperationalInsights/workspaces/{os.environ["LOG_ANALYTICS_NAME"]}'.lower()
if app_insights.get('name') != os.environ['APP_INSIGHTS_NAME'] or app_insights.get('properties', {}).get('provisioningState') != 'Succeeded' or app_insights.get('properties', {}).get('WorkspaceResourceId', '').lower() != expected_workspace_id or app_insights.get('properties', {}).get('IngestionMode') != 'LogAnalytics' or not isinstance(app_insights_connection, str) or not app_insights_connection: raise SystemExit('Application Insights profile drifted')
if log_analytics.get('name') != os.environ['LOG_ANALYTICS_NAME'] or log_analytics.get('properties', {}).get('provisioningState') != 'Succeeded' or log_analytics.get('properties', {}).get('sku', {}).get('name') != 'PerGB2018' or log_analytics.get('properties', {}).get('retentionInDays') != 30: raise SystemExit('Log Analytics workspace profile drifted')
subnets = {subnet.get('name'): subnet for subnet in vnet.get('subnets', [])}
if vnet.get('name') != os.environ['VNET_NAME'] or vnet.get('addressSpace', {}).get('addressPrefixes') != ['10.42.0.0/24'] or set(subnets) != {'aca-infrastructure', 'private-endpoints'} or subnets['aca-infrastructure'].get('addressPrefix') != '10.42.0.0/27' or subnets['private-endpoints'].get('addressPrefix') != '10.42.0.32/27' or subnets['private-endpoints'].get('privateEndpointNetworkPolicies') != 'Disabled': raise SystemExit('virtual network profile drifted')
expected_environment_id = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.App/managedEnvironments/{os.environ["ENVIRONMENT_NAME"]}'.lower()
expected_subnet = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Network/virtualNetworks/{os.environ["VNET_NAME"]}/subnets/aca-infrastructure'.lower()
if environment.get('name') != os.environ['ENVIRONMENT_NAME'] or environment.get('properties', {}).get('vnetConfiguration', {}).get('infrastructureSubnetId', '').lower() != expected_subnet or any(app.get('properties', {}).get('managedEnvironmentId', '').lower() != expected_environment_id for app in apps): raise SystemExit('Container Apps environment private-network profile drifted')
expected_endpoints = {os.environ['COSMOS_PRIVATE_ENDPOINT_NAME'], os.environ['STORAGE_PRIVATE_ENDPOINT_NAME'], os.environ['OPENAI_PRIVATE_ENDPOINT_NAME']}
if not isinstance(private_endpoints, list) or {endpoint.get('name') for endpoint in private_endpoints} != expected_endpoints: raise SystemExit('private endpoint inventory drifted')
nic_names = set()
for endpoint in private_endpoints:
    interfaces = endpoint.get('networkInterfaces')
    if not isinstance(interfaces, list) or len(interfaces) != 1 or not isinstance(interfaces[0].get('id'), str): raise SystemExit('private endpoint NIC inventory drifted')
    nic_names.add(interfaces[0]['id'].rstrip('/').split('/')[-1].lower())
if len(nic_names) != 3: raise SystemExit('private endpoint NIC inventory drifted')
private_subnet = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Network/virtualNetworks/{os.environ["VNET_NAME"]}/subnets/private-endpoints'.lower()
expected_targets = {os.environ['COSMOS_PRIVATE_ENDPOINT_NAME']: (f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.DocumentDB/databaseAccounts/{os.environ["COSMOS_ACCOUNT_NAME"]}'.lower(), 'Sql'), os.environ['STORAGE_PRIVATE_ENDPOINT_NAME']: (f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Storage/storageAccounts/{os.environ["STORAGE_ACCOUNT_NAME"]}'.lower(), 'blob'), os.environ['OPENAI_PRIVATE_ENDPOINT_NAME']: (f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.CognitiveServices/accounts/{os.environ["AOAI_NAME"]}'.lower(), 'account')}
for endpoint in private_endpoints:
    target, group = expected_targets[endpoint['name']]; connections = endpoint.get('privateLinkServiceConnections', [])
    if endpoint.get('provisioningState') != 'Succeeded' or endpoint.get('subnet', {}).get('id', '').lower() != private_subnet or len(connections) != 1 or connections[0].get('privateLinkServiceId', '').lower() != target or connections[0].get('groupIds') != [group] or connections[0].get('privateLinkServiceConnectionState', {}).get('status', '').lower() != 'approved': raise SystemExit('private endpoint wiring drifted')
if not isinstance(zones, list) or {zone.get('name') for zone in zones} != {os.environ['COSMOS_PRIVATE_DNS_ZONE'], os.environ['STORAGE_PRIVATE_DNS_ZONE'], os.environ['OPENAI_PRIVATE_DNS_ZONE'], os.environ['COGNITIVE_SERVICES_PRIVATE_DNS_ZONE'], os.environ['AI_SERVICES_PRIVATE_DNS_ZONE']}: raise SystemExit('private DNS zone inventory drifted')
vnet_id = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Network/virtualNetworks/{os.environ["VNET_NAME"]}'.lower()
if not isinstance(network_security_groups, list): raise SystemExit('tenant-governance NSG profile drifted')
if network_security_groups:
    expected_nsgs = {f'{os.environ["VNET_NAME"]}-aca-infrastructure-nsg-{os.environ["LOCATION"]}'.lower(), f'{os.environ["VNET_NAME"]}-private-endpoints-nsg-{os.environ["LOCATION"]}'.lower()}
    if len(network_security_groups) != len(expected_nsgs) or {nsg.get('name', '').lower() for nsg in network_security_groups} != expected_nsgs or any(nsg.get('provisioningState') != 'Succeeded' or nsg.get('securityRules') != [] or nsg.get('networkInterfaces') not in (None, []) for nsg in network_security_groups): raise SystemExit('tenant-governance NSG profile drifted')
def verify_link(links, zone):
    if len(links) != 1 or links[0].get('name') != os.environ['PRIVATE_DNS_VNET_LINK_NAME'] or links[0].get('provisioningState') != 'Succeeded' or links[0].get('virtualNetworkLinkState') != 'Completed' or links[0].get('registrationEnabled') is not False or links[0].get('virtualNetwork', {}).get('id', '').lower() != vnet_id: raise SystemExit(f'private DNS VNet link drifted: {zone}')
def verify_group(groups, zone, records):
    expected_zone_id = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Network/privateDnsZones/{zone}'.lower()
    if len(groups) != 1 or groups[0].get('name') != 'default' or groups[0].get('provisioningState') != 'Succeeded': raise SystemExit(f'private DNS zone group drifted: {zone}')
    configs = groups[0].get('privateDnsZoneConfigs', [])
    if len(configs) != 1 or configs[0].get('privateDnsZoneId', '').lower() != expected_zone_id or not isinstance(configs[0].get('recordSets'), list) or {record.get('recordSetName') for record in configs[0]['recordSets']} != records: raise SystemExit(f'private DNS zone group wiring drifted: {zone}')
    result = {record['recordSetName']: record.get('ipAddresses') for record in configs[0]['recordSets']}
    if any(not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or not values[0] for values in result.values()): raise SystemExit(f'private DNS zone group address drifted: {zone}')
    return result
def verify_records(records, expected, zone):
    result = {record.get('name'): record.get('aRecords') for record in records}
    if set(result) != expected or any(not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict) or not isinstance(values[0].get('ipv4Address'), str) or not values[0]['ipv4Address'] for values in result.values()): raise SystemExit(f'private DNS A-record inventory drifted: {zone}')
    return {name: [entry.get('ipv4Address') for entry in values] for name, values in result.items()}
verify_link(cosmos_links, os.environ['COSMOS_PRIVATE_DNS_ZONE']); verify_link(storage_links, os.environ['STORAGE_PRIVATE_DNS_ZONE'])
verify_link(openai_links, os.environ['OPENAI_PRIVATE_DNS_ZONE']); verify_link(cognitive_services_links, os.environ['COGNITIVE_SERVICES_PRIVATE_DNS_ZONE']); verify_link(ai_services_links, os.environ['AI_SERVICES_PRIVATE_DNS_ZONE'])
cosmos_names = {os.environ['COSMOS_ACCOUNT_NAME'], f'{os.environ["COSMOS_ACCOUNT_NAME"]}-{os.environ["LOCATION"]}'}
storage_names = {os.environ['STORAGE_ACCOUNT_NAME']}
cosmos_group = verify_group(cosmos_groups, os.environ['COSMOS_PRIVATE_DNS_ZONE'], cosmos_names); storage_group = verify_group(storage_groups, os.environ['STORAGE_PRIVATE_DNS_ZONE'], storage_names)
if cosmos_group != verify_records(cosmos_records, cosmos_names, os.environ['COSMOS_PRIVATE_DNS_ZONE']) or storage_group != verify_records(storage_records, storage_names, os.environ['STORAGE_PRIVATE_DNS_ZONE']): raise SystemExit('private DNS A-record wiring drifted')
account_names = {os.environ['AOAI_NAME']}
account_zones = [os.environ['OPENAI_PRIVATE_DNS_ZONE'], os.environ['COGNITIVE_SERVICES_PRIVATE_DNS_ZONE'], os.environ['AI_SERVICES_PRIVATE_DNS_ZONE']]
def verify_account_group(groups, zone_names, records):
    if len(groups) != 1 or groups[0].get('name') != 'default' or groups[0].get('provisioningState') != 'Succeeded': raise SystemExit('AI account private DNS zone group drifted')
    zone_ids = {f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Network/privateDnsZones/{zone}'.lower(): zone for zone in zone_names}
    configs = groups[0].get('privateDnsZoneConfigs', [])
    if len(configs) != len(zone_names) or {config.get('privateDnsZoneId', '').lower() for config in configs} != set(zone_ids): raise SystemExit('AI account private DNS zone group wiring drifted')
    result = {}
    for config in configs:
        record_sets = config.get('recordSets')
        if not isinstance(record_sets, list) or {record.get('recordSetName') for record in record_sets} != records: raise SystemExit('AI account private DNS zone group wiring drifted')
        mapping = {record['recordSetName']: record.get('ipAddresses') for record in record_sets}
        if any(not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or not values[0] for values in mapping.values()): raise SystemExit('AI account private DNS zone group address drifted')
        result[zone_ids[config['privateDnsZoneId'].lower()]] = mapping
    return result
account_group = verify_account_group(openai_groups, account_zones, account_names)
for zone, zone_records in ((account_zones[0], openai_records), (account_zones[1], cognitive_services_records), (account_zones[2], ai_services_records)):
    if account_group[zone] != verify_records(zone_records, account_names, zone): raise SystemExit('private DNS A-record wiring drifted')
expected_resources = {
  ('microsoft.app/managedenvironments', os.environ['ENVIRONMENT_NAME'].lower()), ('microsoft.app/containerapps', os.environ['FRONTEND_APP_NAME'].lower()), ('microsoft.app/containerapps', os.environ['API_APP_NAME'].lower()), ('microsoft.app/containerapps', os.environ['RUNTIME_APP_NAME'].lower()),
  ('microsoft.managedidentity/userassignedidentities', os.environ['FRONTEND_IDENTITY_NAME'].lower()), ('microsoft.managedidentity/userassignedidentities', os.environ['API_IDENTITY_NAME'].lower()), ('microsoft.managedidentity/userassignedidentities', os.environ['RUNTIME_IDENTITY_NAME'].lower()),
  ('microsoft.operationalinsights/workspaces', os.environ['LOG_ANALYTICS_NAME'].lower()), ('microsoft.insights/components', os.environ['APP_INSIGHTS_NAME'].lower()),
  ('microsoft.containerregistry/registries', os.environ['ACR_NAME'].lower()), ('microsoft.cognitiveservices/accounts', os.environ['AOAI_NAME'].lower()), ('microsoft.documentdb/databaseaccounts', os.environ['COSMOS_ACCOUNT_NAME'].lower()), ('microsoft.storage/storageaccounts', os.environ['STORAGE_ACCOUNT_NAME'].lower()), ('microsoft.network/virtualnetworks', os.environ['VNET_NAME'].lower()), ('microsoft.network/privateendpoints', os.environ['COSMOS_PRIVATE_ENDPOINT_NAME'].lower()), ('microsoft.network/privateendpoints', os.environ['STORAGE_PRIVATE_ENDPOINT_NAME'].lower()), ('microsoft.network/privateendpoints', os.environ['OPENAI_PRIVATE_ENDPOINT_NAME'].lower()), ('microsoft.network/privatednszones', os.environ['COSMOS_PRIVATE_DNS_ZONE'].lower()), ('microsoft.network/privatednszones', os.environ['STORAGE_PRIVATE_DNS_ZONE'].lower()), ('microsoft.network/privatednszones', os.environ['OPENAI_PRIVATE_DNS_ZONE'].lower()), ('microsoft.network/privatednszones', os.environ['COGNITIVE_SERVICES_PRIVATE_DNS_ZONE'].lower()), ('microsoft.network/privatednszones', os.environ['AI_SERVICES_PRIVATE_DNS_ZONE'].lower()),
}
if not isinstance(system_topics, list) or not isinstance(system_topic_subscriptions, list) or len(system_topics) > 1:
    raise SystemExit('tenant-managed Event Grid system topic inventory drifted')
expected_system_topic_resources = set()
if system_topics:
    topic = system_topics[0]
    topic_name = topic.get('name') if isinstance(topic, dict) else None
    expected_topic_prefix = f'{os.environ["STORAGE_ACCOUNT_NAME"]}-'
    try:
        valid_topic_name = isinstance(topic_name, str) and topic_name.startswith(expected_topic_prefix) and str(uuid.UUID(topic_name[len(expected_topic_prefix):])) == topic_name[len(expected_topic_prefix):]
    except (ValueError, AttributeError):
        valid_topic_name = False
    expected_source = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.Storage/storageAccounts/{os.environ["STORAGE_ACCOUNT_NAME"]}'.lower()
    if not valid_topic_name or topic.get('provisioningState') != 'Succeeded' or topic.get('source', '').lower() != expected_source or topic.get('topicType', '').lower() != 'microsoft.storage.storageaccounts':
        raise SystemExit('tenant-managed Event Grid system topic inventory drifted')
    if len(system_topic_subscriptions) != 1:
        raise SystemExit('Defender Storage Antimalware subscription inventory drifted')
    subscription = system_topic_subscriptions[0]
    expected_subscription = {
        'name': 'StorageAntimalwareSubscription',
        'provisioningState': 'Succeeded',
        'destination': {
            'endpointType': 'WebHook',
            'endpointBaseUrl': f'https://{os.environ["LOCATION"]}.a3.storageav.azure.com:5142/EventCapture/{os.environ["SUBSCRIPTION_ID"]}/{os.environ["STORAGE_ACCOUNT_NAME"]}',
            'aadApplication': 'f1f8da5f-609a-401d-85b2-d498116b7265',
            'aadTenant': '33e01921-4d64-4f8c-a055-5bdaffd5e33d',
            'maxEventsPerBatch': 1,
            'preferredBatchSizeInKilobytes': 64,
            'deliveryAttributeMappings': None,
        },
        'eventDeliverySchema': 'EventGridSchema',
        'filter': {
            'advancedFilters': [{'key': 'data.blobType', 'operatorType': 'StringContains', 'values': ['BlockBlob']}],
            'enableAdvancedFilteringOnArrays': None,
            'includedEventTypes': ['Microsoft.Storage.BlobCreated', 'Microsoft.Storage.BlobRenamed'],
            'isSubjectCaseSensitive': None,
            'subjectBeginsWith': '',
            'subjectEndsWith': '',
        },
        'retryPolicy': {'eventTimeToLiveInMinutes': 1440, 'maxDeliveryAttempts': 30},
        'deadLetterDestination': None,
        'deadLetterWithResourceIdentity': None,
        'deliveryWithResourceIdentity': None,
        'expirationTimeUtc': None,
        'labels': None,
    }
    if subscription != expected_subscription:
        raise SystemExit('Defender Storage Antimalware subscription inventory drifted')
    expected_system_topic_resources.add(('microsoft.eventgrid/systemtopics', topic_name.lower()))
elif system_topic_subscriptions:
    raise SystemExit('Defender Storage Antimalware subscription inventory drifted')
expected_resources |= expected_system_topic_resources
expected_resources |= {('microsoft.network/networkinterfaces', name) for name in nic_names}
if network_security_groups:
    expected_resources |= {('microsoft.network/networksecuritygroups', name) for name in expected_nsgs}
actual_resources = {(r.get('type', '').lower(), r.get('name', '').lower()) for r in resources if isinstance(r, dict)}
allowed_children = {('microsoft.documentdb/databaseaccounts/sqldatabases', f'{os.environ["COSMOS_ACCOUNT_NAME"]}/{os.environ["DATABASE_NAME"]}'.lower()), ('microsoft.documentdb/databaseaccounts/sqldatabases/containers', f'{os.environ["COSMOS_ACCOUNT_NAME"]}/{os.environ["DATABASE_NAME"]}/appstate'.lower()), ('microsoft.cognitiveservices/accounts/deployments', f'{os.environ["AOAI_NAME"]}/{os.environ["MODEL_DEPLOYMENT_NAME"]}'.lower()), ('microsoft.cognitiveservices/accounts/deployments', f'{os.environ["AOAI_NAME"]}/{os.environ["LEGACY_MODEL_DEPLOYMENT_NAME"]}'.lower()), ('microsoft.cognitiveservices/accounts/projects', f'{os.environ["AOAI_NAME"]}/{os.environ["FOUNDRY_PROJECT_NAME"]}'.lower()), ('microsoft.network/privatednszones/virtualnetworklinks', f'{os.environ["COSMOS_PRIVATE_DNS_ZONE"]}/{os.environ["PRIVATE_DNS_VNET_LINK_NAME"]}'.lower()), ('microsoft.network/privatednszones/virtualnetworklinks', f'{os.environ["STORAGE_PRIVATE_DNS_ZONE"]}/{os.environ["PRIVATE_DNS_VNET_LINK_NAME"]}'.lower()), ('microsoft.network/privatednszones/virtualnetworklinks', f'{os.environ["OPENAI_PRIVATE_DNS_ZONE"]}/{os.environ["PRIVATE_DNS_VNET_LINK_NAME"]}'.lower()), ('microsoft.network/privatednszones/virtualnetworklinks', f'{os.environ["COGNITIVE_SERVICES_PRIVATE_DNS_ZONE"]}/{os.environ["PRIVATE_DNS_VNET_LINK_NAME"]}'.lower()), ('microsoft.network/privatednszones/virtualnetworklinks', f'{os.environ["AI_SERVICES_PRIVATE_DNS_ZONE"]}/{os.environ["PRIVATE_DNS_VNET_LINK_NAME"]}'.lower()), ('microsoft.network/privateendpoints/privatednszonegroups', f'{os.environ["COSMOS_PRIVATE_ENDPOINT_NAME"]}/default'.lower()), ('microsoft.network/privateendpoints/privatednszonegroups', f'{os.environ["STORAGE_PRIVATE_ENDPOINT_NAME"]}/default'.lower()), ('microsoft.network/privateendpoints/privatednszonegroups', f'{os.environ["OPENAI_PRIVATE_ENDPOINT_NAME"]}/default'.lower()), ('microsoft.storage/storageaccounts/blobservices', f'{os.environ["STORAGE_ACCOUNT_NAME"]}/default'.lower()), ('microsoft.storage/storageaccounts/blobservices/containers', f'{os.environ["STORAGE_ACCOUNT_NAME"]}/default/engagement-artifacts'.lower()), ('microsoft.alertsmanagement/smartdetectoralertrules', f'failure anomalies - {os.environ["APP_INSIGHTS_NAME"]}'.lower())}
if not expected_resources <= actual_resources or any(resource not in expected_resources | allowed_children for resource in actual_resources): raise SystemExit('required resource inventory drifted')
rg_scope = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/'.lower()
if any(not item.get('scope', '').lower().startswith(rg_scope) for item in assignments): raise SystemExit('managed identity role assignment escapes the resource group')
expected_roles = {(f'{rg_scope}providers/Microsoft.ContainerRegistry/registries/{os.environ["ACR_NAME"]}'.lower(), 'acrpull', os.environ['FRONTEND_PRINCIPAL'].lower()), (f'{rg_scope}providers/Microsoft.ContainerRegistry/registries/{os.environ["ACR_NAME"]}'.lower(), 'acrpull', os.environ['API_PRINCIPAL'].lower()), (f'{rg_scope}providers/Microsoft.ContainerRegistry/registries/{os.environ["ACR_NAME"]}'.lower(), 'acrpull', os.environ['RUNTIME_PRINCIPAL'].lower()), (f'{rg_scope}providers/Microsoft.Storage/storageAccounts/{os.environ["STORAGE_ACCOUNT_NAME"]}'.lower(), 'storage blob data contributor', os.environ['API_PRINCIPAL'].lower()), (f'{rg_scope}providers/Microsoft.CognitiveServices/accounts/{os.environ["AOAI_NAME"]}'.lower(), 'cognitive services openai user', os.environ['RUNTIME_PRINCIPAL'].lower())}
actual_roles = {(item.get('scope', '').lower(), item.get('roleDefinitionName', '').lower(), item.get('principalId', '').lower()) for item in assignments}
if actual_roles != expected_roles: raise SystemExit('managed identity role assignments drifted')
cosmos_scope = f'/subscriptions/{os.environ["SUBSCRIPTION_ID"]}/resourceGroups/{os.environ["RESOURCE_GROUP"]}/providers/Microsoft.DocumentDB/databaseAccounts/{os.environ["COSMOS_ACCOUNT_NAME"]}'
expected_cosmos = {(f'{cosmos_scope}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002', cosmos_scope, os.environ['API_PRINCIPAL']), (f'{cosmos_scope}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002', cosmos_scope, os.environ['RUNTIME_PRINCIPAL'])}
actual_cosmos = {(item.get('roleDefinitionId', ''), item.get('scope', ''), item.get('principalId', '')) for item in cosmos_assignments}
if actual_cosmos != expected_cosmos: raise SystemExit('Cosmos SQL role assignments drifted')
