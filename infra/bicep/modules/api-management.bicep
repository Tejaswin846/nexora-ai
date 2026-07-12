param name string
param location string
param publisherName string
param publisherEmail string
param backendUrl string
@secure()
param backendSharedSecret string
param tags object = {}

resource service 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Developer'
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: 'Enabled'
    virtualNetworkType: 'None'
    disableGateway: false
  }
}

resource backendSecret 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: service
  name: 'backend-shared-secret'
  properties: {
    displayName: 'backend-shared-secret'
    secret: true
    value: backendSharedSecret
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: service
  name: 'software-staging-v1'
  properties: {
    displayName: 'Software Staging API'
    apiRevision: '1'
    apiVersion: 'v1'
    apiVersionSetId: versionSet.id
    description: 'Pillar 1 staging gateway for the Software FastAPI application.'
    format: 'openapi-link'
    path: ''
    protocols: [
      'https'
    ]
    serviceUrl: backendUrl
    subscriptionRequired: false
    value: '${backendUrl}/openapi.json'
  }
}

resource versionSet 'Microsoft.ApiManagement/service/apiVersionSets@2024-05-01' = {
  parent: service
  name: 'software-staging'
  properties: {
    displayName: 'Software Staging'
    versioningScheme: 'Header'
    versionHeaderName: 'X-API-Version'
  }
}

output id string = service.id
output name string = service.name
output apiName string = api.name
output gatewayHostname string = '${service.name}.azure-api.net'
output gatewayUrl string = 'https://${service.name}.azure-api.net'
