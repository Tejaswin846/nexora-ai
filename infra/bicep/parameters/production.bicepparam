using '../main.bicep'

param projectName = 'software'
param environmentName = 'production'
param location = 'centralindia'
param staticWebAppLocation = 'eastasia'
param frontDoorSku = 'Premium_AzureFrontDoor'
param apiManagementSku = 'Standard'
param staticWebAppSku = 'Standard'
param containerRegistrySku = 'Standard'
param serviceBusSku = 'Standard'
param storageReplicationType = 'Standard_ZRS'
param apiMinReplicas = 2
param apiMaxReplicas = 10
param workerMinReplicas = 1
param workerMaxReplicas = 10
param enableManagedWafRules = true
param enableFrontDoor = true
param enableApiManagement = true
param logRetentionInDays = 30
param logDailyQuotaGb = '5'
param deployWorkloads = false
