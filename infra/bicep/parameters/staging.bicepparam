using '../main.bicep'

param projectName = 'software'
param environmentName = 'staging'
param location = 'centralindia'
param staticWebAppLocation = 'eastasia'
param frontDoorSku = 'Standard_AzureFrontDoor'
param apiManagementSku = 'Consumption'
param staticWebAppSku = 'Free'
param containerRegistrySku = 'Basic'
param serviceBusSku = 'Standard'
param storageReplicationType = 'Standard_LRS'
param apiMinReplicas = 0
param apiMaxReplicas = 2
param workerMinReplicas = 0
param workerMaxReplicas = 2
param enableManagedWafRules = false
param enableFrontDoor = true

// Consumption lacks rate-limit-by-key. The required staging fallback bypasses APIM.
param enableApiManagement = false
param logRetentionInDays = 30
param logDailyQuotaGb = '0.5'
param deployWorkloads = false
