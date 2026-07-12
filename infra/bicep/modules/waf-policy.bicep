param name string
@allowed([
  'Standard_AzureFrontDoor'
  'Premium_AzureFrontDoor'
])
param frontDoorSku string = 'Standard_AzureFrontDoor'
param enableManagedRules bool = false
param tags object = {}

var managedRuleConfiguration = enableManagedRules ? {
  managedRules: {
    managedRuleSets: [
      {
        ruleSetType: 'Microsoft_DefaultRuleSet'
        ruleSetVersion: '2.1'
        ruleSetAction: 'Log'
      }
      {
        ruleSetType: 'Microsoft_BotManagerRuleSet'
        ruleSetVersion: '1.1'
        ruleSetAction: 'Log'
      }
    ]
  }
} : {}

resource waf 'Microsoft.Network/frontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: name
  location: 'Global'
  tags: tags
  sku: {
    name: frontDoorSku
  }
  properties: union({
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Detection'
      requestBodyCheck: 'Enabled'
      javascriptChallengeExpirationInMinutes: 30
    }
    customRules: {
      rules: [
        {
          name: 'ApiAbuseRateLimit'
          action: 'Block'
          enabledState: 'Enabled'
          priority: 100
          ruleType: 'RateLimitRule'
          rateLimitDurationInMinutes: 1
          rateLimitThreshold: 300
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'BeginsWith'
              matchValue: [
                '/api/'
              ]
              negateCondition: false
              transforms: [
                'Lowercase'
              ]
            }
          ]
        }
        {
          name: 'LogUnexpectedHttpMethods'
          action: 'Log'
          enabledState: 'Enabled'
          priority: 110
          ruleType: 'MatchRule'
          matchConditions: [
            {
              matchVariable: 'RequestMethod'
              operator: 'Equal'
              matchValue: [
                'TRACE'
                'TRACK'
              ]
              negateCondition: false
              transforms: []
            }
          ]
        }
      ]
    }
  }, managedRuleConfiguration)
}

output id string = waf.id
output name string = waf.name
output mode string = waf.properties.policySettings.mode
