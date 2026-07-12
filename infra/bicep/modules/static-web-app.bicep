param name string
param location string = 'eastasia'
param tags object = {}

resource staticSite 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    allowConfigFileUpdates: true
    enterpriseGradeCdnStatus: 'Disabled'
    publicNetworkAccess: 'Enabled'
    stagingEnvironmentPolicy: 'Enabled'
  }
}

output id string = staticSite.id
output name string = staticSite.name
output defaultHostname string = staticSite.properties.defaultHostname
