targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string
param frontendIdentityName string
param apiIdentityName string
param runtimeIdentityName string
param virtualNetworkName string
param cosmosPrivateEndpointName string
param storagePrivateEndpointName string
param openAiPrivateEndpointName string
param privateDnsVnetLinkName string
param databaseName string
param cosmosAccountName string
param storageAccountName string
param acrName string
param acrLocation string
param azureOpenAiName string
@minLength(1)
@maxLength(64)
param azureOpenAiDeploymentName string
@minLength(1)
@maxLength(128)
param azureOpenAiModelName string
@minLength(1)
@maxLength(128)
param azureOpenAiModelVersion string
@minLength(1)
@maxLength(64)
param azureOpenAiModelSkuName string
@minValue(1)
@maxValue(1000000)
param azureOpenAiModelCapacity int
@minLength(2)
@maxLength(64)
param foundryProjectName string
@minLength(1)
@maxLength(64)
param legacyModelDeploymentName string
@minLength(1)
@maxLength(128)
param legacyModelName string
@minLength(1)
@maxLength(128)
param legacyModelVersion string
@minLength(1)
@maxLength(64)
param legacyModelSkuName string
@minValue(1)
@maxValue(1000000)
param legacyModelCapacity int
param acaInfrastructureNsgId string = ''
param privateEndpointNsgId string = ''

var containerName = 'appstate'
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'
var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var acaInfrastructureSubnetName = 'aca-infrastructure'
var privateEndpointSubnetName = 'private-endpoints'
var cosmosPrivateDnsZoneName = 'privatelink.documents.azure.com'
// This is the Azure public-cloud Private Link suffix required by the approved Storage endpoint.
#disable-next-line no-hardcoded-env-urls
var storagePrivateDnsZoneName = 'privatelink.blob.core.windows.net'
// The AIServices account private endpoint publishes all three data-plane FQDN families.
var openAiPrivateDnsZoneName = 'privatelink.openai.azure.com'
var cognitiveServicesPrivateDnsZoneName = 'privatelink.cognitiveservices.azure.com'
var aiServicesPrivateDnsZoneName = 'privatelink.services.ai.azure.com'

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: virtualNetworkName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.42.0.0/24'
      ]
    }
    subnets: [
      {
        name: acaInfrastructureSubnetName
        properties: union({
          addressPrefix: '10.42.0.0/27'
          delegations: [
            {
              name: 'aca-environment'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }, empty(acaInfrastructureNsgId) ? {} : {
          networkSecurityGroup: {
            id: acaInfrastructureNsgId
          }
        })
      }
      {
        name: privateEndpointSubnetName
        properties: union({
          addressPrefix: '10.42.0.32/27'
          privateEndpointNetworkPolicies: 'Disabled'
        }, empty(privateEndpointNsgId) ? {} : {
          networkSecurityGroup: {
            id: privateEndpointNsgId
          }
        })
      }
    ]
  }
}

resource acaInfrastructureSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: virtualNetwork
  name: acaInfrastructureSubnetName
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: virtualNetwork
  name: privateEndpointSubnetName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: null
      logAnalyticsConfiguration: null
    }
    vnetConfiguration: {
      infrastructureSubnetId: acaInfrastructureSubnet.id
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource frontendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: frontendIdentityName
  location: location
}

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: apiIdentityName
  location: location
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: runtimeIdentityName
  location: location
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: acrLocation
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource azureOpenAi 'Microsoft.CognitiveServices/accounts@2026-05-01' = {
  name: azureOpenAiName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: azureOpenAiName
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    allowProjectManagement: true
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2026-05-01' = {
  parent: azureOpenAi
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource azureOpenAiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: azureOpenAi
  name: azureOpenAiDeploymentName
  sku: {
    name: azureOpenAiModelSkuName
    capacity: azureOpenAiModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: azureOpenAiModelName
      version: azureOpenAiModelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// Retained for instant rollback of the model binding; deployments on one account must
// be created serially, so this depends on the primary deployment.
resource azureOpenAiLegacyDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: azureOpenAi
  name: legacyModelDeploymentName
  sku: {
    name: legacyModelSkuName
    capacity: legacyModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: legacyModelName
      version: legacyModelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [
    azureOpenAiDeployment
  ]
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    enableAutomaticFailover: true
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/sessionId'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'engagement-artifacts'
  properties: {
    publicAccess: 'None'
  }
}

resource cosmosPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: cosmosPrivateDnsZoneName
  location: 'global'
}

resource storagePrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: storagePrivateDnsZoneName
  location: 'global'
}

resource openAiPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: openAiPrivateDnsZoneName
  location: 'global'
}

resource cognitiveServicesPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: cognitiveServicesPrivateDnsZoneName
  location: 'global'
}

resource aiServicesPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: aiServicesPrivateDnsZoneName
  location: 'global'
}

resource cosmosPrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: cosmosPrivateDnsZone
  name: privateDnsVnetLinkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: virtualNetwork.id
    }
    registrationEnabled: false
  }
}

resource storagePrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: storagePrivateDnsZone
  name: privateDnsVnetLinkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: virtualNetwork.id
    }
    registrationEnabled: false
  }
}

resource openAiPrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: openAiPrivateDnsZone
  name: privateDnsVnetLinkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: virtualNetwork.id
    }
    registrationEnabled: false
  }
}

resource cognitiveServicesPrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: cognitiveServicesPrivateDnsZone
  name: privateDnsVnetLinkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: virtualNetwork.id
    }
    registrationEnabled: false
  }
}

resource aiServicesPrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: aiServicesPrivateDnsZone
  name: privateDnsVnetLinkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: virtualNetwork.id
    }
    registrationEnabled: false
  }
}

resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: cosmosPrivateEndpointName
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmos-sql'
        properties: {
          privateLinkServiceId: cosmos.id
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
}

resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: storagePrivateEndpointName
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource cosmosPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: cosmosPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cosmos'
        properties: {
          privateDnsZoneId: cosmosPrivateDnsZone.id
        }
      }
    ]
  }
}

resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: storagePrivateDnsZone.id
        }
      }
    ]
  }
}

// The private-link connection mutates the account's provisioning state, so it must not
// run while project or model-deployment writes are in flight on the same account.
resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: openAiPrivateEndpointName
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'openai-account'
        properties: {
          privateLinkServiceId: azureOpenAi.id
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
  dependsOn: [
    foundryProject
    azureOpenAiLegacyDeployment
  ]
}

resource openAiPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: openAiPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'openai'
        properties: {
          privateDnsZoneId: openAiPrivateDnsZone.id
        }
      }
      {
        name: 'cognitiveservices'
        properties: {
          privateDnsZoneId: cognitiveServicesPrivateDnsZone.id
        }
      }
      {
        name: 'aiservices'
        properties: {
          privateDnsZoneId: aiServicesPrivateDnsZone.id
        }
      }
    ]
  }
}

module acrRoles 'acr-roles.bicep' = {
  name: 'acr-roles'
  params: {
    acrName: acrName
    frontendPrincipalId: frontendIdentity.properties.principalId
    apiPrincipalId: apiIdentity.properties.principalId
    runtimePrincipalId: runtimeIdentity.properties.principalId
  }
  dependsOn: [
    acr
  ]
}

module openAiRole 'openai-role.bicep' = {
  name: 'openai-role'
  params: {
    accountName: azureOpenAiName
    runtimePrincipalId: runtimeIdentity.properties.principalId
    assignmentSeed: runtimeIdentityName
  }
  dependsOn: [
    azureOpenAi
  ]
}

resource apiCosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, apiIdentityName, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: apiIdentity.properties.principalId
    scope: cosmos.id
  }
}

resource runtimeCosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, runtimeIdentityName, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: runtimeIdentity.properties.principalId
    scope: cosmos.id
  }
}

resource apiBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, apiIdentityName, blobDataContributorRoleId)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output environmentDefaultDomain string = environment.properties.defaultDomain
output environmentId string = environment.id
output cosmosAccountName string = cosmos.name
output cosmosEndpoint string = 'https://${cosmos.name}.documents.azure.com:443/'
output storageAccountName string = storage.name
output acrName string = acr.name
output storageBlobEndpoint string = storage.properties.primaryEndpoints.blob
output acrLoginServer string = acr.properties.loginServer
output azureOpenAiName string = azureOpenAi.name
output azureOpenAiEndpoint string = azureOpenAi.properties.endpoint
output azureOpenAiDeploymentName string = azureOpenAiDeployment.name
output foundryProjectName string = foundryProject.name
output frontendIdentityId string = frontendIdentity.id
output frontendIdentityClientId string = frontendIdentity.properties.clientId
output frontendIdentityPrincipalId string = frontendIdentity.properties.principalId
output apiIdentityId string = apiIdentity.id
output apiIdentityClientId string = apiIdentity.properties.clientId
output apiIdentityPrincipalId string = apiIdentity.properties.principalId
output runtimeIdentityId string = runtimeIdentity.id
output runtimeIdentityClientId string = runtimeIdentity.properties.clientId
output runtimeIdentityPrincipalId string = runtimeIdentity.properties.principalId
