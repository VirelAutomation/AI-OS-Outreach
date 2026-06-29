import { workflow, trigger, node, outputParser, expr, newCredential } from '@n8n/workflow-sdk';

const intakeWebhook = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Business Intel Webhook',
    position: [240, 300],
    parameters: {
      httpMethod: 'POST',
      path: 'virel-business-intel',
      authentication: 'none',
      responseMode: 'responseNode',
    },
  },
  output: [{
    body: {
      niche: 'digital marketing agency',
      city: 'Mumbai',
      query: 'digital marketing agencies in Mumbai phone email website',
      maxResults: 10,
    },
  }],
});

const normalizeRequest = node({
  type: 'n8n-nodes-base.set',
  version: 3.4,
  config: {
    name: 'Normalize Request',
    position: [520, 300],
    parameters: {
      mode: 'manual',
      includeOtherFields: true,
      assignments: {
        assignments: [
          { id: 'niche', name: 'niche', value: expr('{{ $json.body?.niche ?? "digital marketing agency" }}'), type: 'string' },
          { id: 'city', name: 'city', value: expr('{{ $json.body?.city ?? "Mumbai" }}'), type: 'string' },
          { id: 'query', name: 'search_query', value: expr('{{ $json.body?.query ?? (($json.body?.niche ?? "digital marketing agency") + " in " + ($json.body?.city ?? "Mumbai") + " phone email website") }}'), type: 'string' },
          { id: 'max', name: 'max_results', value: expr('{{ Number($json.body?.maxResults ?? 10) }}'), type: 'number' },
          { id: 'provider', name: 'search_provider_url', value: 'https://google.serper.dev/search', type: 'string' },
          { id: 'country', name: 'country_code', value: expr('{{ $json.body?.countryCode ?? "in" }}'), type: 'string' },
        ],
      },
    },
  },
  output: [{
    niche: 'digital marketing agency',
    city: 'Mumbai',
    search_query: 'digital marketing agencies in Mumbai phone email website',
    max_results: 10,
    search_provider_url: 'https://google.serper.dev/search',
    country_code: 'in',
  }],
});

const runSearch = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Run Search Provider',
    position: [820, 300],
    parameters: {
      method: 'POST',
      url: expr('{{ $json.search_provider_url }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendHeaders: true,
      specifyHeaders: 'keypair',
      headerParameters: {
        parameters: [
          { name: 'Content-Type', value: 'application/json' },
        ],
      },
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { q: $json.search_query, num: $json.max_results, gl: $json.country_code, hl: "en" } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
    credentials: {
      httpHeaderAuth: newCredential('Search Provider API Key'),
    },
  },
  output: [{
    organic: [
      {
        title: 'Virel Media',
        link: 'https://example.com',
        snippet: 'Phone +91 98765 43210 Email hello@example.com',
      },
    ],
  }],
});

const normalizeResults = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Normalize Search Results',
    position: [1120, 300],
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: "const source = $input.first().json;\nconst candidates = source.organic ?? source.places ?? source.results ?? source.data ?? [];\nconst phoneRegex = /(?:\\+?\\d[\\d\\s().-]{7,}\\d)/g;\nconst emailRegex = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/ig;\nreturn candidates.map((item, index) => {\n  const title = item.title ?? item.name ?? item.company_name ?? `lead-${index + 1}`;\n  const link = item.link ?? item.website ?? item.url ?? '';\n  const snippet = item.snippet ?? item.description ?? item.address ?? '';\n  const phones = `${item.phoneNumber ?? item.phone ?? ''} ${snippet}`.match(phoneRegex) ?? [];\n  const emails = `${item.email ?? ''} ${snippet}`.match(emailRegex) ?? [];\n  return {\n    json: {\n      company_name: String(title).trim(),\n      niche: $('Normalize Request').first().json.niche,\n      city: $('Normalize Request').first().json.city,\n      website: link,\n      phone: phones[0] ?? '',\n      email: emails[0] ?? '',\n      source_url: link,\n      source_query: $('Normalize Request').first().json.search_query,\n      lead_score: link ? 75 : 45,\n      status: 'discovered',\n      last_seen_at: $now.toISO(),\n    },\n  };\n});",
    },
  },
  output: [{
    company_name: 'Virel Media',
    niche: 'digital marketing agency',
    city: 'Mumbai',
    website: 'https://example.com',
    phone: '+91 98765 43210',
    email: 'hello@example.com',
    source_url: 'https://example.com',
    source_query: 'digital marketing agencies in Mumbai phone email website',
    lead_score: 75,
    status: 'discovered',
    last_seen_at: '2026-06-23T00:00:00.000Z',
  }],
});

const persistBusinesses = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Persist Business Intel',
    position: [1420, 300],
    parameters: {
      resource: 'row',
      operation: 'upsert',
      dataTableId: {
        __rl: true,
        mode: 'id',
        value: 'RsD2My3qXhLKNdx3',
      },
      matchType: 'allConditions',
      filters: {
        conditions: [
          { keyName: 'company_name', condition: 'eq', keyValue: expr('{{ $json.company_name }}') },
          { keyName: 'website', condition: 'eq', keyValue: expr('{{ $json.website }}') },
        ],
      },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          company_name: expr('{{ $json.company_name }}'),
          niche: expr('{{ $json.niche }}'),
          city: expr('{{ $json.city }}'),
          website: expr('{{ $json.website }}'),
          phone: expr('{{ $json.phone }}'),
          email: expr('{{ $json.email }}'),
          source_url: expr('{{ $json.source_url }}'),
          source_query: expr('{{ $json.source_query }}'),
          lead_score: expr('{{ $json.lead_score }}'),
          status: expr('{{ $json.status }}'),
          last_seen_at: expr('{{ $json.last_seen_at }}'),
        },
      },
    },
  },
  output: [{
    company_name: 'Virel Media',
    niche: 'digital marketing agency',
    city: 'Mumbai',
    website: 'https://example.com',
    phone: '+91 98765 43210',
    email: 'hello@example.com',
    source_url: 'https://example.com',
    source_query: 'digital marketing agencies in Mumbai phone email website',
    lead_score: 75,
    status: 'discovered',
    last_seen_at: '2026-06-23T00:00:00.000Z',
  }],
});

const respond = node({
  type: 'n8n-nodes-base.respondToWebhook',
  version: 1.5,
  config: {
    name: 'Return Results',
    position: [1720, 300],
    parameters: {
      respondWith: 'allIncomingItems',
      options: {
        responseKey: 'businesses',
        responseCode: 200,
      },
    },
  },
});

export default workflow('virel-business-intel-harvest', 'Virel - Business Intel Harvest')
  .add(intakeWebhook)
  .to(normalizeRequest)
  .to(runSearch)
  .to(normalizeResults)
  .to(persistBusinesses)
  .to(respond);
