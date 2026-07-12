param name string
param location string
param tags object = {}
param retentionInDays int = 30
@allowed([
  '0.5'
  '1'
  '5'
])
param dailyQuotaGb string = '0.5'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    workspaceCapping: {
      dailyQuotaGb: json(dailyQuotaGb)
    }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource ingestionAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${name}-ingestion-growth'
  location: 'global'
  tags: tags
  properties: {
    description: 'Detect unexpected Log Analytics ingestion before the daily cap is reached.'
    severity: 2
    enabled: true
    scopes: [
      workspace.id
    ]
    evaluationFrequency: 'PT1H'
    windowSize: 'PT6H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'UnexpectedDataCollectionVolume'
          metricNamespace: 'Microsoft.OperationalInsights/workspaces'
          metricName: 'Data Collection Volume'
          operator: 'GreaterThan'
          threshold: 100000000
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    autoMitigate: true
    actions: []
  }
}

output id string = workspace.id
output name string = workspace.name
output customerId string = workspace.properties.customerId
