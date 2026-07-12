param name string
param location string
param environmentId string
param image string
param registryServer string
param identityId string
param identityClientId string
param serviceBusNamespace string
param serviceBusQueueName string
param storageAccountUrl string
param gitCommitSha string
param buildTimestamp string
param tags object = {}
param minReplicas int = 0
param maxReplicas int = 3

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: registryServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'staging' }
            { name: 'GIT_COMMIT_SHA', value: gitCommitSha }
            { name: 'BUILD_TIMESTAMP', value: buildTimestamp }
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
            { name: 'AZURE_SERVICE_BUS_QUEUE_NAME', value: serviceBusQueueName }
            { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
            { name: 'LOG_LEVEL', value: 'INFO' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'service-bus-queue'
            custom: {
              type: 'azure-servicebus'
              identity: identityId
              metadata: {
                namespace: serviceBusNamespace
                queueName: serviceBusQueueName
                messageCount: '5'
              }
            }
          }
        ]
      }
    }
  }
}

output id string = app.id
output name string = app.name
output latestRevisionName string = app.properties.latestRevisionName
