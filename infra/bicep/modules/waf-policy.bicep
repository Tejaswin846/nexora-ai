param name string
param tags object = {}

resource waf 'Microsoft.Network/frontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: name
  location: 'Global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
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
      ]
    }
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
  }
}

output id string = waf.id
output name string = waf.name
output mode string = waf.properties.policySettings.mode
