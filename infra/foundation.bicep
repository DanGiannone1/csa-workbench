targetScope = 'subscription'

@description('Clean-break isolated MVP instance identifier.')
@minLength(3)
@maxLength(10)
param instanceSlug string
param location string
param acrLocation string
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
param enableFoundryProject bool = false
param enableLegacyModel bool = false
@maxLength(64)
param legacyModelDeploymentName string = ''
@maxLength(128)
param legacyModelName string = ''
@maxLength(128)
param legacyModelVersion string = ''
@maxLength(64)
param legacyModelSkuName string = ''
@minValue(1)
@maxValue(1000000)
param legacyModelCapacity int = 1
@description('Existing tenant-governance NSG ID to preserve on the ACA infrastructure subnet, or empty when absent.')
param acaInfrastructureNsgId string = ''
@description('Existing tenant-governance NSG ID to preserve on the private-endpoints subnet, or empty when absent.')
param privateEndpointNsgId string = ''

var baseName = 'csa-wb-${instanceSlug}'
var globalStem = 'csawb${uniqueString(subscription().subscriptionId, instanceSlug)}'
var resourceGroupName = '${baseName}-rg'
var environmentName = '${baseName}-env'
var frontendAppName = '${baseName}-frontend'
var apiAppName = '${baseName}-api'
var runtimeAppName = '${baseName}-runtime'
var frontendIdentityName = '${baseName}-frontend-identity'
var apiIdentityName = '${baseName}-api-identity'
var runtimeIdentityName = '${baseName}-runtime-identity'
var virtualNetworkName = '${baseName}-vnet'
var cosmosPrivateEndpointName = '${baseName}-cosmos-pe'
var storagePrivateEndpointName = '${baseName}-storage-pe'
var openAiPrivateEndpointName = '${baseName}-openai-pe'
var privateDnsVnetLinkName = '${baseName}-vnet-link'
var databaseName = '${baseName}-entra'
var acrName = globalStem
var cosmosAccountName = globalStem
var storageAccountName = globalStem
var azureOpenAiName = 'csawb-${uniqueString(subscription().subscriptionId, instanceSlug)}'
var logAnalyticsName = '${baseName}-logs'
var appInsightsName = '${baseName}-insights'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

module platform 'platform.bicep' = {
  name: 'platform-${instanceSlug}'
  scope: resourceGroup
  params: {
    location: location
    environmentName: environmentName
    frontendIdentityName: frontendIdentityName
    apiIdentityName: apiIdentityName
    runtimeIdentityName: runtimeIdentityName
    virtualNetworkName: virtualNetworkName
    cosmosPrivateEndpointName: cosmosPrivateEndpointName
    storagePrivateEndpointName: storagePrivateEndpointName
    openAiPrivateEndpointName: openAiPrivateEndpointName
    privateDnsVnetLinkName: privateDnsVnetLinkName
    databaseName: databaseName
    cosmosAccountName: cosmosAccountName
    storageAccountName: storageAccountName
    acrName: acrName
    acrLocation: acrLocation
    azureOpenAiName: azureOpenAiName
    azureOpenAiDeploymentName: azureOpenAiDeploymentName
    azureOpenAiModelName: azureOpenAiModelName
    azureOpenAiModelVersion: azureOpenAiModelVersion
    azureOpenAiModelSkuName: azureOpenAiModelSkuName
    azureOpenAiModelCapacity: azureOpenAiModelCapacity
    enableFoundryProject: enableFoundryProject
    foundryProjectName: foundryProjectName
    enableLegacyModel: enableLegacyModel
    legacyModelDeploymentName: legacyModelDeploymentName
    legacyModelName: legacyModelName
    legacyModelVersion: legacyModelVersion
    legacyModelSkuName: legacyModelSkuName
    legacyModelCapacity: legacyModelCapacity
    acaInfrastructureNsgId: acaInfrastructureNsgId
    privateEndpointNsgId: privateEndpointNsgId
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
  }
}

output resourceGroupName string = resourceGroup.name
output logAnalyticsName string = logAnalyticsName
output appInsightsName string = appInsightsName
output appInsightsConnectionString string = platform.outputs.appInsightsConnectionString
output environmentName string = environmentName
output frontendAppName string = frontendAppName
output apiAppName string = apiAppName
output runtimeAppName string = runtimeAppName
output virtualNetworkName string = virtualNetworkName
output cosmosPrivateEndpointName string = cosmosPrivateEndpointName
output storagePrivateEndpointName string = storagePrivateEndpointName
output openAiPrivateEndpointName string = openAiPrivateEndpointName
output privateDnsVnetLinkName string = privateDnsVnetLinkName
output databaseName string = databaseName
output environmentDefaultDomain string = platform.outputs.environmentDefaultDomain
output environmentId string = platform.outputs.environmentId
output cosmosAccountName string = platform.outputs.cosmosAccountName
output cosmosEndpoint string = platform.outputs.cosmosEndpoint
output storageAccountName string = platform.outputs.storageAccountName
output storageBlobEndpoint string = platform.outputs.storageBlobEndpoint
output acrName string = platform.outputs.acrName
output acrLoginServer string = platform.outputs.acrLoginServer
output azureOpenAiName string = platform.outputs.azureOpenAiName
output azureOpenAiEndpoint string = platform.outputs.azureOpenAiEndpoint
output azureOpenAiDeploymentName string = platform.outputs.azureOpenAiDeploymentName
output foundryProjectName string = platform.outputs.foundryProjectName
output frontendIdentityName string = frontendIdentityName
output frontendIdentityId string = platform.outputs.frontendIdentityId
output frontendIdentityClientId string = platform.outputs.frontendIdentityClientId
output frontendIdentityPrincipalId string = platform.outputs.frontendIdentityPrincipalId
output apiIdentityName string = apiIdentityName
output apiIdentityId string = platform.outputs.apiIdentityId
output apiIdentityClientId string = platform.outputs.apiIdentityClientId
output apiIdentityPrincipalId string = platform.outputs.apiIdentityPrincipalId
output runtimeIdentityName string = runtimeIdentityName
output runtimeIdentityId string = platform.outputs.runtimeIdentityId
output runtimeIdentityClientId string = platform.outputs.runtimeIdentityClientId
output runtimeIdentityPrincipalId string = platform.outputs.runtimeIdentityPrincipalId
