param location string
param apiIdentityName string
param workerIdentityName string
param deployerIdentityName string
param githubOrganization string = ''
param githubRepository string = ''
param githubEnvironment string = 'staging'

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: apiIdentityName
  location: location
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: workerIdentityName
  location: location
}

resource deployerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: deployerIdentityName
  location: location
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = if (!empty(githubOrganization) && !empty(githubRepository)) {
  parent: deployerIdentity
  name: 'github-${githubEnvironment}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubOrganization}/${githubRepository}:environment:${githubEnvironment}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

output apiIdentityId string = apiIdentity.id
output apiPrincipalId string = apiIdentity.properties.principalId
output apiClientId string = apiIdentity.properties.clientId
output workerIdentityId string = workerIdentity.id
output workerPrincipalId string = workerIdentity.properties.principalId
output workerClientId string = workerIdentity.properties.clientId
output deployerIdentityId string = deployerIdentity.id
output deployerPrincipalId string = deployerIdentity.properties.principalId
output deployerClientId string = deployerIdentity.properties.clientId
