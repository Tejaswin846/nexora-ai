param name string
param location string
param tags object = {}
param softDeleteDays int = 14
@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
  'Standard_GZRS'
])
param replicationType string = 'Standard_LRS'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: replicationType
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

resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          enabled: true
          name: 'delete-temporary-staging-artifacts'
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 14
                }
              }
              snapshot: {
                delete: {
                  daysAfterCreationGreaterThan: 14
                }
              }
              version: {
                delete: {
                  daysAfterCreationGreaterThan: 14
                }
              }
            }
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'workflow-artifacts/temporary/'
              ]
            }
          }
        }
      ]
    }
  }
}

output id string = storage.id
output name string = storage.name
output accountUrl string = 'https://${storage.name}.blob.${environment().suffixes.storage}'
output containerNames array = containerNames
