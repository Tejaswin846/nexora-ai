param registryName string
param serviceBusNamespaceName string
param storageAccountName string
param apiPrincipalId string
param workerPrincipalId string
param deployerPrincipalId string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' existing = {
  name: serviceBusNamespaceName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var acrPushRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
var serviceBusSenderRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
var serviceBusReceiverRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6c40b7-bf2f-4c3f-b1e1-4be3b258e7a6')
var blobContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, apiPrincipalId, acrPullRole)
  scope: registry
  properties: {
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRole
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, workerPrincipalId, acrPullRole)
  scope: registry
  properties: {
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRole
  }
}

resource deployerAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(registry.id, deployerPrincipalId, acrPushRole)
  scope: registry
  properties: {
    principalId: deployerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRole
  }
}

resource apiServiceBusSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBus.id, apiPrincipalId, serviceBusSenderRole)
  scope: serviceBus
  properties: {
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusSenderRole
  }
}

resource workerServiceBusReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBus.id, workerPrincipalId, serviceBusReceiverRole)
  scope: serviceBus
  properties: {
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusReceiverRole
  }
}

resource apiBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, apiPrincipalId, blobContributorRole)
  scope: storage
  properties: {
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobContributorRole
  }
}

resource workerBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, workerPrincipalId, blobContributorRole)
  scope: storage
  properties: {
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobContributorRole
  }
}

output assignmentIds array = [
  apiAcrPull.id
  workerAcrPull.id
  apiServiceBusSender.id
  workerServiceBusReceiver.id
  apiBlobContributor.id
  workerBlobContributor.id
]
