targetScope = 'subscription'

@description('Short project name used in generated resource names.')
param projectName string = 'software'

@allowed([
  'staging'
  'production'
])
param environmentName string = 'staging'

param location string = 'centralindia'
param staticWebAppLocation string = 'eastasia'
param uniqueSuffix string = take(uniqueString(subscription().subscriptionId, projectName, environmentName), 6)
param resourceGroupName string = 'rg-${projectName}-${environmentName}'
param apimPublisherName string = 'Software Platform'
param apimPublisherEmail string = 'azure-admin@example.com'
param appVersion string = '0.1.0'
param gitCommitSha string = 'bootstrap'
param buildTimestamp string = 'unknown'
param apiImageTag string = 'bootstrap'
param workerImageTag string = 'bootstrap'
param frontDoorHostname string = ''
param expectedFrontDoorId string = ''
param deployerPrincipalId string = ''
param deployWorkloads bool = false

@allowed([
  'Standard_AzureFrontDoor'
  'Premium_AzureFrontDoor'
])
param frontDoorSku string = 'Standard_AzureFrontDoor'

@allowed([
  'Consumption'
  'Developer'
  'Basic'
  'Standard'
  'Premium'
])
param apiManagementSku string = 'Consumption'

@allowed([
  'Free'
  'Standard'
])
param staticWebAppSku string = 'Free'

@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param containerRegistrySku string = 'Basic'

@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param serviceBusSku string = 'Standard'

@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
  'Standard_GZRS'
])
param storageReplicationType string = 'Standard_LRS'

@minValue(0)
@maxValue(10)
param apiMinReplicas int = 0

@minValue(1)
@maxValue(10)
param apiMaxReplicas int = 2

@minValue(0)
@maxValue(10)
param workerMinReplicas int = 0

@minValue(1)
@maxValue(10)
param workerMaxReplicas int = 2

param enableManagedWafRules bool = false
param enableFrontDoor bool = true
param enableApiManagement bool = false
param logRetentionInDays int = 30
@allowed([
  '0.5'
  '1'
  '5'
])
param logDailyQuotaGb string = '0.5'

@secure()
param supabaseUrl string = ''
@secure()
param supabaseAnonKey string = ''
@secure()
param supabaseServiceRoleKey string = ''
@secure()
param databaseUrl string = ''
@secure()
param upstashUrl string = ''
@secure()
param upstashToken string = ''
@secure()
param authSecret string = ''
@secure()
param posthogKey string = ''
@secure()
param apimBackendSharedSecret string = ''

var configurationIsValid = (!enableManagedWafRules || frontDoorSku == 'Premium_AzureFrontDoor') && (apiMinReplicas <= apiMaxReplicas) && (workerMinReplicas <= workerMaxReplicas) && (serviceBusSku != 'Basic')

var normalizedProject = toLower(replace(projectName, '-', ''))
var compactEnvironment = environmentName == 'staging' ? 'stg' : 'prd'
var registryName = take('acr${normalizedProject}${compactEnvironment}${uniqueSuffix}', 50)
var storageAccountName = take('st${normalizedProject}${compactEnvironment}${uniqueSuffix}', 24)
var logAnalyticsName = 'log-${projectName}-${environmentName}-${uniqueSuffix}'
var containerEnvironmentName = 'cae-${projectName}-${environmentName}-${uniqueSuffix}'
var apiAppName = 'ca-${projectName}-api-${environmentName}-${uniqueSuffix}'
var workerAppName = 'ca-${projectName}-worker-${environmentName}-${uniqueSuffix}'
var serviceBusName = 'sb-${projectName}-${environmentName}-${uniqueSuffix}'
var staticWebAppName = 'swa-${projectName}-${environmentName}-${uniqueSuffix}'
var apiManagementName = 'apim-${projectName}-${environmentName}-${uniqueSuffix}'
var frontDoorProfileName = 'afd-${projectName}-${environmentName}-${uniqueSuffix}'
var frontDoorEndpointName = 'software-${environmentName}-${uniqueSuffix}'
var wafPolicyName = 'waf-${projectName}-${environmentName}-${uniqueSuffix}'
var apiIdentityName = 'id-${projectName}-api-${environmentName}-${uniqueSuffix}'
var workerIdentityName = 'id-${projectName}-worker-${environmentName}-${uniqueSuffix}'
var commonTags = {
  project: projectName
  environment: environmentName
  pillar: '1'
  managedBy: 'bicep'
  costProfile: environmentName == 'staging' ? 'lean' : 'production'
}

resource targetResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: commonTags
}

module identities 'modules/identities.bicep' = {
  name: 'identities'
  scope: targetResourceGroup
  params: {
    location: location
    apiIdentityName: apiIdentityName
    workerIdentityName: workerIdentityName
    tags: commonTags
  }
}

module registry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: targetResourceGroup
  params: {
    name: registryName
    location: location
    skuName: containerRegistrySku
    tags: commonTags
  }
}

module logs 'modules/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: targetResourceGroup
  params: {
    name: logAnalyticsName
    location: location
    retentionInDays: logRetentionInDays
    dailyQuotaGb: logDailyQuotaGb
    tags: commonTags
  }
}

module containerEnvironment 'modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: targetResourceGroup
  params: {
    name: containerEnvironmentName
    location: location
    logAnalyticsWorkspaceName: logs.outputs.name
    tags: commonTags
  }
}

module serviceBus 'modules/service-bus.bicep' = {
  name: 'service-bus'
  scope: targetResourceGroup
  params: {
    namespaceName: serviceBusName
    queueName: 'workflow-jobs'
    location: location
    skuName: serviceBusSku
    tags: commonTags
  }
}

module storage 'modules/blob-storage.bicep' = {
  name: 'blob-storage'
  scope: targetResourceGroup
  params: {
    name: storageAccountName
    location: location
    replicationType: storageReplicationType
    tags: commonTags
  }
}

module staticWeb 'modules/static-web-app.bicep' = {
  name: 'static-web-app'
  scope: targetResourceGroup
  params: {
    name: staticWebAppName
    location: staticWebAppLocation
    skuName: staticWebAppSku
    tags: commonTags
  }
}

module roles 'modules/role-assignments.bicep' = {
  name: 'role-assignments'
  scope: targetResourceGroup
  params: {
    registryName: registry.outputs.name
    serviceBusNamespaceName: serviceBus.outputs.name
    storageAccountName: storage.outputs.name
    apiPrincipalId: identities.outputs.apiPrincipalId
    workerPrincipalId: identities.outputs.workerPrincipalId
    deployerPrincipalId: deployerPrincipalId
  }
}

var apiImage = '${registry.outputs.loginServer}/api:${apiImageTag}'
var workerImage = '${registry.outputs.loginServer}/worker:${workerImageTag}'
var allowedOrigins = empty(frontDoorHostname)
  ? 'https://${staticWeb.outputs.defaultHostname}'
  : 'https://${staticWeb.outputs.defaultHostname},https://${frontDoorHostname}'
var approvedGatewayMode = enableApiManagement ? 'apim' : (enableFrontDoor ? 'frontdoor' : 'none')

module apiApp 'modules/container-app-api.bicep' = if (deployWorkloads && configurationIsValid) {
  name: 'container-app-api'
  scope: targetResourceGroup
  params: {
    name: apiAppName
    location: location
    environmentId: containerEnvironment.outputs.id
    image: apiImage
    registryServer: registry.outputs.loginServer
    identityId: identities.outputs.apiIdentityId
    identityClientId: identities.outputs.apiClientId
    serviceBusNamespace: serviceBus.outputs.fqdn
    serviceBusQueueName: serviceBus.outputs.queueName
    storageAccountUrl: storage.outputs.accountUrl
    allowedOrigins: allowedOrigins
    approvedGatewayMode: approvedGatewayMode
    expectedFrontDoorId: expectedFrontDoorId
    appVersion: appVersion
    gitCommitSha: gitCommitSha
    buildTimestamp: buildTimestamp
    minReplicas: apiMinReplicas
    maxReplicas: apiMaxReplicas
    supabaseUrl: supabaseUrl
    supabaseAnonKey: supabaseAnonKey
    supabaseServiceRoleKey: supabaseServiceRoleKey
    databaseUrl: databaseUrl
    upstashUrl: upstashUrl
    upstashToken: upstashToken
    authSecret: authSecret
    posthogKey: posthogKey
    apimBackendKey: apimBackendSharedSecret
    tags: commonTags
  }
  dependsOn: [roles]
}

module workerApp 'modules/container-app-worker.bicep' = if (deployWorkloads && configurationIsValid) {
  name: 'container-app-worker'
  scope: targetResourceGroup
  params: {
    name: workerAppName
    location: location
    environmentId: containerEnvironment.outputs.id
    image: workerImage
    registryServer: registry.outputs.loginServer
    identityId: identities.outputs.workerIdentityId
    identityClientId: identities.outputs.workerClientId
    serviceBusNamespace: serviceBus.outputs.fqdn
    serviceBusQueueName: serviceBus.outputs.queueName
    storageAccountUrl: storage.outputs.accountUrl
    gitCommitSha: gitCommitSha
    buildTimestamp: buildTimestamp
    minReplicas: workerMinReplicas
    maxReplicas: workerMaxReplicas
    tags: commonTags
  }
  dependsOn: [roles]
}

module apiManagement 'modules/api-management.bicep' = if (deployWorkloads && enableApiManagement) {
  name: 'api-management'
  scope: targetResourceGroup
  params: {
    name: apiManagementName
    location: location
    skuName: apiManagementSku
    publisherName: apimPublisherName
    publisherEmail: apimPublisherEmail
    backendUrl: 'https://${apiApp!.outputs.fqdn}'
    backendSharedSecret: apimBackendSharedSecret
    tags: commonTags
  }
}

module waf 'modules/waf-policy.bicep' = if (deployWorkloads && enableFrontDoor) {
  name: 'waf-policy'
  scope: targetResourceGroup
  params: {
    name: wafPolicyName
    frontDoorSku: frontDoorSku
    enableManagedRules: enableManagedWafRules
    tags: commonTags
  }
}

module frontDoor 'modules/front-door.bicep' = if (deployWorkloads && enableFrontDoor) {
  name: 'front-door'
  scope: targetResourceGroup
  params: {
    profileName: frontDoorProfileName
    endpointName: frontDoorEndpointName
    profileSku: frontDoorSku
    apiOriginHostname: enableApiManagement ? apiManagement!.outputs.gatewayHostname : apiApp!.outputs.fqdn
    apiOriginName: enableApiManagement ? 'api-management' : 'container-apps-api'
    staticWebAppHostname: staticWeb.outputs.defaultHostname
    wafPolicyId: waf!.outputs.id
    logAnalyticsWorkspaceId: logs.outputs.id
    tags: commonTags
  }
}

module apiPolicy 'modules/api-management-policy.bicep' = if (deployWorkloads && enableApiManagement && enableFrontDoor) {
  name: 'api-management-policy'
  scope: targetResourceGroup
  params: {
    apiManagementName: apiManagement!.outputs.name
    apiName: apiManagement!.outputs.apiName
    backendUrl: 'https://${apiApp!.outputs.fqdn}'
    expectedFrontDoorId: frontDoor!.outputs.frontDoorId
  }
}

output resourceGroupName string = targetResourceGroup.name
output selectedRegion string = location
output staticWebAppRegion string = staticWebAppLocation
output selectedSkus object = {
  frontDoor: enableFrontDoor ? frontDoorSku : 'disabled'
  apiManagement: enableApiManagement ? apiManagementSku : 'disabled'
  staticWebApp: staticWebAppSku
  containerRegistry: containerRegistrySku
  serviceBus: serviceBusSku
  storage: storageReplicationType
}
output registryName string = registry.outputs.name
output registryLoginServer string = registry.outputs.loginServer
output apiIdentityClientId string = identities.outputs.apiClientId
output workerIdentityClientId string = identities.outputs.workerClientId
output serviceBusNamespace string = serviceBus.outputs.fqdn
output serviceBusQueueName string = serviceBus.outputs.queueName
output storageAccountName string = storage.outputs.name
output blobContainers array = storage.outputs.containerNames
output staticWebAppHostname string = staticWeb.outputs.defaultHostname
output apiContainerAppHostname string = deployWorkloads ? apiApp!.outputs.fqdn : ''
output workerContainerAppName string = deployWorkloads ? workerApp!.outputs.name : ''
output apiManagementHostname string = deployWorkloads && enableApiManagement ? apiManagement!.outputs.gatewayHostname : ''
output frontDoorHostname string = deployWorkloads && enableFrontDoor ? frontDoor!.outputs.endpointHostname : ''
output frontDoorId string = deployWorkloads && enableFrontDoor ? frontDoor!.outputs.frontDoorId : ''
output wafMode string = deployWorkloads && enableFrontDoor ? waf!.outputs.mode : 'not-deployed'
