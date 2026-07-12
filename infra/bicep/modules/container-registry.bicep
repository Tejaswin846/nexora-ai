param name string
param location string
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Basic'
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    adminUserEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    publicNetworkAccess: 'Enabled'
  }
}

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer
