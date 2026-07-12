param name string
param location string
param environmentId string
param image string
param registryServer string
param identityId string
param identityClientId string
param serviceBusNamespace string
param serviceBusQueueName string
param storageAccountUrl string
param allowedOrigins string
param appVersion string
param gitCommitSha string
param buildTimestamp string
@secure()
param supabaseUrl string
@secure()
param supabaseAnonKey string
@secure()
param supabaseServiceRoleKey string
@secure()
param databaseUrl string
@secure()
param upstashUrl string
@secure()
param upstashToken string
@secure()
param authSecret string
@secure()
param posthogKey string
@secure()
param apimBackendKey string
param tags object = {}
param minReplicas int = 0
param maxReplicas int = 2

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Multiple'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 8000
        transport: 'Auto'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: registryServer
          identity: identityId
        }
      ]
      secrets: [
        { name: 'supabase-url', value: supabaseUrl }
        { name: 'supabase-anon-key', value: supabaseAnonKey }
        { name: 'supabase-service-role-key', value: supabaseServiceRoleKey }
        { name: 'database-url', value: databaseUrl }
        { name: 'upstash-url', value: upstashUrl }
        { name: 'upstash-token', value: upstashToken }
        { name: 'auth-secret', value: authSecret }
        { name: 'posthog-key', value: posthogKey }
        { name: 'apim-backend-key', value: apimBackendKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'HOST', value: '0.0.0.0' }
            { name: 'PORT', value: '8000' }
            { name: 'NEXORA_ENV', value: 'staging' }
            { name: 'ENVIRONMENT', value: 'staging' }
            { name: 'APP_VERSION', value: appVersion }
            { name: 'GIT_COMMIT_SHA', value: gitCommitSha }
            { name: 'BUILD_TIMESTAMP', value: buildTimestamp }
            { name: 'CORS_ALLOWED_ORIGINS', value: allowedOrigins }
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
            { name: 'AZURE_SERVICE_BUS_QUEUE_NAME', value: serviceBusQueueName }
            { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
            { name: 'SUPABASE_URL', secretRef: 'supabase-url' }
            { name: 'SUPABASE_ANON_KEY', secretRef: 'supabase-anon-key' }
            { name: 'SUPABASE_SERVICE_ROLE_KEY', secretRef: 'supabase-service-role-key' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'UPSTASH_REDIS_REST_URL', secretRef: 'upstash-url' }
            { name: 'UPSTASH_REDIS_REST_TOKEN', secretRef: 'upstash-token' }
            { name: 'NEXORA_AUTH_SECRET', secretRef: 'auth-secret' }
            { name: 'POSTHOG_PROJECT_API_KEY', secretRef: 'posthog-key' }
            { name: 'POSTHOG_CAPTURE_PROMPTS', value: 'false' }
            { name: 'POSTHOG_CAPTURE_RESPONSES', value: 'false' }
            { name: 'POSTHOG_PRIVACY_MODE', value: 'true' }
            { name: 'APIM_BACKEND_SHARED_SECRET', secretRef: 'apim-backend-key' }
            { name: 'REQUIRE_APIM_BACKEND_HEADER', value: 'true' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health/live'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/ready'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              timeoutSeconds: 5
              failureThreshold: 4
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '40'
              }
            }
          }
        ]
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output latestRevisionName string = app.properties.latestRevisionName
