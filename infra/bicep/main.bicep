targetScope = 'subscription'

@description('Short project name used in generated resource names.')
param projectName string = 'software'

@allowed([
  'staging'
])
param environmentName string = 'staging'

param location string = 'centralindia'
param staticWebAppLocation string = 'eastasia'
param uniqueSuffix string = take(uniqueString(subscription().subscriptionId, projectName, environmentName), 6)
param resourceGroupName string = 'rg-${projectName}-${environmentName}-${uniqueSuffix}'
param githubOrganization string = ''
param githubRepository string = ''
param githubEnvironment string = 'staging'
param apimPublisherName string = 'Software Platform'
param apimPublisherEmail string = 'azure-admin@example.com'
param appVersion string = '0.1.0'
param gitCommitSha string = 'bootstrap'
param buildTimestamp string = 'unknown'
param apiImageTag string = 'bootstrap'
param workerImageTag string = 'bootstrap'
param frontDoorHostname string = ''
param deployWorkloads bool = false
param premiumFrontDoorCostApproved bool = false

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

var normalizedProject = toLower(replace(projectName, '-', ''))
var compactEnvironment = environmentName == 'staging' ? 'stg' : take(environmentName, 3)
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
var deployerIdentityName = 'id-${projectName}-github-${environmentName}-${uniqueSuffix}'
var commonTags = {
  project: projectName
  environment: environmentName
  pillar: '1'
  managedBy: 'bicep'
}

resource stagingResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: commonTags
}

module identities 'modules/identities.bicep' = {
  name: 'identities'
  scope: stagingResourceGroup
  params: {
    location: location
    apiIdentityName: apiIdentityName
    workerIdentityName: workerIdentityName
    deployerIdentityName: deployerIdentityName
    githubOrganization: githubOrganization
    githubRepository: githubRepository
    githubEnvironment: githubEnvironment
  }
}

module registry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: stagingResourceGroup
  params: {
    name: registryName
    location: location
    tags: commonTags
  }
}

module logs 'modules/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: stagingResourceGroup
  params: {
    name: logAnalyticsName
    location: location
    tags: commonTags
  }
}

module containerEnvironment 'modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: stagingResourceGroup
  params: {
    name: containerEnvironmentName
    location: location
    logAnalyticsWorkspaceName: logs.outputs.name
    tags: commonTags
  }
}

module serviceBus 'modules/service-bus.bicep' = {
  name: 'service-bus'
  scope: stagingResourceGroup
  params: {
    namespaceName: serviceBusName
    queueName: 'workflow-jobs'
    location: location
    tags: commonTags
  }
}

module storage 'modules/blob-storage.bicep' = {
  name: 'blob-storage'
  scope: stagingResourceGroup
  params: {
    name: storageAccountName
    location: location
    tags: commonTags
  }
}

module staticWeb 'modules/static-web-app.bicep' = {
  name: 'static-web-app'
  scope: stagingResourceGroup
  params: {
    name: staticWebAppName
    location: staticWebAppLocation
    tags: commonTags
  }
}

module roles 'modules/role-assignments.bicep' = {
  name: 'role-assignments'
  scope: stagingResourceGroup
  params: {
    registryName: registry.outputs.name
    serviceBusNamespaceName: serviceBus.outputs.name
    storageAccountName: storage.outputs.name
    apiPrincipalId: identities.outputs.apiPrincipalId
    workerPrincipalId: identities.outputs.workerPrincipalId
    deployerPrincipalId: identities.outputs.deployerPrincipalId
  }
}

var apiImage = '${registry.outputs.loginServer}/api:${apiImageTag}'
var workerImage = '${registry.outputs.loginServer}/worker:${workerImageTag}'
var allowedOrigins = empty(frontDoorHostname)
  ? 'https://${staticWeb.outputs.defaultHostname}'
  : 'https://${staticWeb.outputs.defaultHostname},https://${frontDoorHostname}'
module apiApp 'modules/container-app-api.bicep' = if (deployWorkloads) {
  name: 'container-app-api'
  scope: stagingResourceGroup
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
    appVersion: appVersion
    gitCommitSha: gitCommitSha
    buildTimestamp: buildTimestamp
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
  dependsOn: [
    roles
  ]
}

module workerApp 'modules/container-app-worker.bicep' = if (deployWorkloads) {
  name: 'container-app-worker'
  scope: stagingResourceGroup
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
    tags: commonTags
  }
  dependsOn: [
    roles
  ]
}

module apiManagement 'modules/api-management.bicep' = if (deployWorkloads && premiumFrontDoorCostApproved) {
  name: 'api-management'
  scope: stagingResourceGroup
  params: {
    name: apiManagementName
    location: location
    publisherName: apimPublisherName
    publisherEmail: apimPublisherEmail
    backendUrl: 'https://${apiApp!.outputs.fqdn}'
    backendSharedSecret: apimBackendSharedSecret
    tags: commonTags
  }
}

module waf 'modules/waf-policy.bicep' = if (deployWorkloads && premiumFrontDoorCostApproved) {
  name: 'waf-policy'
  scope: stagingResourceGroup
  params: {
    name: wafPolicyName
    tags: commonTags
  }
}

module frontDoor 'modules/front-door.bicep' = if (deployWorkloads && premiumFrontDoorCostApproved) {
  name: 'front-door'
  scope: stagingResourceGroup
  params: {
    profileName: frontDoorProfileName
    endpointName: frontDoorEndpointName
    apiManagementHostname: apiManagement!.outputs.gatewayHostname
    staticWebAppHostname: staticWeb.outputs.defaultHostname
    wafPolicyId: waf!.outputs.id
    logAnalyticsWorkspaceId: logs.outputs.id
    tags: commonTags
  }
}

module apiPolicy 'modules/api-management-policy.bicep' = if (deployWorkloads && premiumFrontDoorCostApproved) {
  name: 'api-management-policy'
  scope: stagingResourceGroup
  params: {
    apiManagementName: apiManagement!.outputs.name
    apiName: apiManagement!.outputs.apiName
    backendUrl: 'https://${apiApp!.outputs.fqdn}'
    expectedFrontDoorId: frontDoor!.outputs.frontDoorId
  }
}

output resourceGroupName string = stagingResourceGroup.name
output selectedRegion string = location
output staticWebAppRegion string = staticWebAppLocation
output registryName string = registry.outputs.name
output registryLoginServer string = registry.outputs.loginServer
output apiIdentityClientId string = identities.outputs.apiClientId
output workerIdentityClientId string = identities.outputs.workerClientId
output deployerIdentityClientId string = identities.outputs.deployerClientId
output serviceBusNamespace string = serviceBus.outputs.fqdn
output serviceBusQueueName string = serviceBus.outputs.queueName
output storageAccountName string = storage.outputs.name
output blobContainers array = storage.outputs.containerNames
output staticWebAppHostname string = staticWeb.outputs.defaultHostname
output apiContainerAppHostname string = deployWorkloads ? apiApp!.outputs.fqdn : ''
output workerContainerAppName string = deployWorkloads ? workerApp!.outputs.name : ''
output apiManagementHostname string = deployWorkloads && premiumFrontDoorCostApproved ? apiManagement!.outputs.gatewayHostname : ''
output frontDoorHostname string = deployWorkloads && premiumFrontDoorCostApproved ? frontDoor!.outputs.endpointHostname : ''
output wafMode string = deployWorkloads && premiumFrontDoorCostApproved ? waf!.outputs.mode : 'not-deployed'
