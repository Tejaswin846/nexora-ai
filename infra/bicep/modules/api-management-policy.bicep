param apiManagementName string
param apiName string
param backendUrl string
param expectedFrontDoorId string

resource service 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apiManagementName
}

resource api 'Microsoft.ApiManagement/service/apis@2024-05-01' existing = {
  parent: service
  name: apiName
}

resource backendUrlValue 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: service
  name: 'software-backend-url'
  properties: {
    displayName: 'software-backend-url'
    secret: false
    value: backendUrl
  }
}

resource frontDoorIdValue 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: service
  name: 'expected-front-door-id'
  properties: {
    displayName: 'expected-front-door-id'
    secret: false
    value: expectedFrontDoorId
  }
}

resource policy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '''
<policies>
  <inbound>
    <base />
    <choose>
      <when condition="@(context.Request.Headers.GetValueOrDefault(&quot;X-Azure-FDID&quot;, &quot;&quot;) != &quot;{{expected-front-door-id}}&quot;)">
        <return-response>
          <set-status code="403" reason="Forbidden" />
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"error":{"code":"front_door_required","message":"Use the approved staging endpoint."}}</set-body>
        </return-response>
      </when>
      <when condition="@(context.Request.Url.Path.StartsWith(&quot;/settings&quot;) || context.Request.Url.Path.StartsWith(&quot;/system&quot;) || context.Request.Url.Path.StartsWith(&quot;/memory&quot;) || context.Request.Url.Path.StartsWith(&quot;/persona&quot;) || context.Request.Url.Path.StartsWith(&quot;/behavior&quot;) || context.Request.Url.Path.StartsWith(&quot;/nexora-core&quot;) || context.Request.Url.Path.StartsWith(&quot;/agi&quot;))">
        <return-response>
          <set-status code="404" reason="Not Found" />
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"error":{"code":"not_found","message":"Route is not publicly available."}}</set-body>
        </return-response>
      </when>
      <when condition="@(context.Request.Headers.ContainsKey(&quot;Content-Length&quot;) &amp;&amp; long.Parse(context.Request.Headers.GetValueOrDefault(&quot;Content-Length&quot;, &quot;0&quot;)) &gt; 1048576)">
        <return-response>
          <set-status code="413" reason="Payload Too Large" />
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"error":{"code":"payload_too_large","message":"Request body exceeds the staging limit."}}</set-body>
        </return-response>
      </when>
    </choose>
    <set-variable name="correlation-id" value="@(context.Request.Headers.GetValueOrDefault(&quot;X-Correlation-ID&quot;, Guid.NewGuid().ToString()))" />
    <set-header name="X-Correlation-ID" exists-action="override"><value>@((string)context.Variables["correlation-id"])</value></set-header>
    <set-header name="X-APIM-Backend-Key" exists-action="override"><value>{{backend-shared-secret}}</value></set-header>
    <rate-limit-by-key calls="120" renewal-period="60" counter-key="@(context.Request.Headers.GetValueOrDefault(&quot;X-Organization-ID&quot;, context.Request.IpAddress))" />
    <set-backend-service base-url="{{software-backend-url}}" />
  </inbound>
  <backend>
    <forward-request timeout="60" fail-on-error-status-code="false" />
  </backend>
  <outbound>
    <base />
    <set-header name="X-Correlation-ID" exists-action="override"><value>@((string)context.Variables["correlation-id"])</value></set-header>
    <set-header name="Server" exists-action="delete" />
    <set-header name="X-Powered-By" exists-action="delete" />
  </outbound>
  <on-error>
    <base />
    <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
    <set-header name="X-Correlation-ID" exists-action="override"><value>@((string)context.Variables.GetValueOrDefault("correlation-id", Guid.NewGuid().ToString()))</value></set-header>
  </on-error>
</policies>
'''
  }
}
