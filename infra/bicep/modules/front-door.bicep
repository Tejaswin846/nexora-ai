param profileName string
param endpointName string
param apiManagementHostname string
param staticWebAppHostname string
param wafPolicyId string
param logAnalyticsWorkspaceId string
param tags object = {}

resource profile 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: profileName
  location: 'global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    originResponseTimeoutSeconds: 60
  }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: profile
  name: endpointName
  location: 'global'
  properties: {
    enabledState: 'Enabled'
  }
}

resource apiOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: profile
  name: 'api-origin-group'
  properties: {
    healthProbeSettings: {
      probeIntervalInSeconds: 30
      probePath: '/health/live'
      probeProtocol: 'Https'
      probeRequestType: 'GET'
    }
    loadBalancingSettings: {
      additionalLatencyInMilliseconds: 50
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    sessionAffinityState: 'Disabled'
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: apiOriginGroup
  name: 'api-management'
  properties: {
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
    hostName: apiManagementHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: apiManagementHostname
    priority: 1
    weight: 1000
  }
}

resource frontendOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: profile
  name: 'frontend-origin-group'
  properties: {
    healthProbeSettings: {
      probeIntervalInSeconds: 60
      probePath: '/index.html'
      probeProtocol: 'Https'
      probeRequestType: 'GET'
    }
    loadBalancingSettings: {
      additionalLatencyInMilliseconds: 50
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    sessionAffinityState: 'Disabled'
  }
}

resource frontendOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: frontendOriginGroup
  name: 'static-web-app'
  properties: {
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
    hostName: staticWebAppHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: staticWebAppHostname
    priority: 1
    weight: 1000
  }
}

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'api-route'
  properties: {
    cacheConfiguration: null
    enabledState: 'Enabled'
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
    originGroup: {
      id: apiOriginGroup.id
    }
    patternsToMatch: [
      '/api/*'
      '/auth/*'
      '/agi/*'
      '/artifacts*'
      '/automation/*'
      '/behavior*'
      '/capabilities'
      '/chat*'
      '/email/*'
      '/feedback'
      '/files/*'
      '/finance'
      '/health/*'
      '/image/*'
      '/legacy-health'
      '/memory*'
      '/models'
      '/nexora-core/*'
      '/persona*'
      '/projects*'
      '/reminders*'
      '/run-agent'
      '/search*'
      '/sessions*'
      '/settings/*'
      '/study/*'
      '/system/*'
      '/upload'
      '/version'
      '/website/*'
      '/workflow/*'
      '/workflows*'
      '/openapi.json'
    ]
    supportedProtocols: [
      'Http'
      'Https'
    ]
  }
  dependsOn: [
    apiOrigin
  ]
}

resource frontendRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'frontend-route'
  properties: {
    cacheConfiguration: {
      compressionSettings: {
        contentTypesToCompress: [
          'text/html'
          'text/css'
          'application/javascript'
          'application/json'
          'image/svg+xml'
        ]
        isCompressionEnabled: true
      }
      queryStringCachingBehavior: 'UseQueryString'
    }
    enabledState: 'Enabled'
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
    originGroup: {
      id: frontendOriginGroup.id
    }
    patternsToMatch: [
      '/*'
    ]
    supportedProtocols: [
      'Http'
      'Https'
    ]
  }
  dependsOn: [
    frontendOrigin
  ]
}

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  parent: profile
  name: 'waf-security-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      associations: [
        {
          domains: [
            {
              id: endpoint.id
            }
          ]
          patternsToMatch: [
            '/*'
          ]
        }
      ]
      wafPolicy: {
        id: wafPolicyId
      }
    }
  }
  dependsOn: [
    apiRoute
    frontendRoute
  ]
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'front-door-diagnostics'
  scope: profile
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'FrontDoorAccessLog', enabled: true }
      { category: 'FrontDoorHealthProbeLog', enabled: true }
      { category: 'FrontDoorWebApplicationFirewallLog', enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

output id string = profile.id
output name string = profile.name
output frontDoorId string = profile.properties.frontDoorId
output endpointHostname string = endpoint.properties.hostName
