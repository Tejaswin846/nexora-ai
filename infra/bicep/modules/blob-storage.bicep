param name string
param location string
param tags object = {}
param softDeleteDays int = 14

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Cool'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    containerDeleteRetentionPolicy: {
      enabled: true
      days: softDeleteDays
    }
    deleteRetentionPolicy: {
      enabled: true
      days: softDeleteDays
    }
    isVersioningEnabled: true
  }
}

var containerNames = [
  'benchmark-exports'
  'audit-exports'
  'workflow-artifacts'
  'customer-reports'
]

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for containerName in containerNames: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

output id string = storage.id
output name string = storage.name
output accountUrl string = 'https://${storage.name}.blob.${environment().suffixes.storage}'
output containerNames array = containerNames
