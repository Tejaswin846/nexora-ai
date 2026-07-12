param namespaceName string
param queueName string = 'workflow-jobs'
param location string
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Standard'
param tags object = {}

resource namespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuName
    capacity: skuName == 'Premium' ? 1 : 0
  }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
  }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: namespace
  name: queueName
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: skuName != 'Basic'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    enableBatchedOperations: true
    enablePartitioning: false
    maxSizeInMegabytes: 1024
  }
}

output id string = namespace.id
output name string = namespace.name
output fqdn string = '${namespace.name}.servicebus.windows.net'
output queueName string = queue.name
