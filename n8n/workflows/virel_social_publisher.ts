import { workflow, trigger, node, splitInBatches, nextBatch, ifElse, switchCase, expr, newCredential } from '@n8n/workflow-sdk';

const publishTrigger = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.3,
  config: {
    name: 'Every 30 Minutes',
    position: [240, 420],
    parameters: {
      rule: {
        interval: [
          {
            field: 'minutes',
            minutesInterval: 30,
          },
        ],
      },
    },
  },
  output: [{}],
});

const loadQueue = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Load Social Queue',
    position: [520, 420],
    parameters: {
      resource: 'row',
      operation: 'get',
      dataTableId: {
        __rl: true,
        mode: 'id',
        value: '8PRuj7rfE2FDYkzR',
      },
      returnAll: true,
      orderBy: true,
      orderByColumn: 'publish_at',
      orderByDirection: 'ASC',
    },
  },
  output: [{
    content_id: 'content-ig-1',
    platform: 'instagram',
    title: 'Why AI is now mandatory',
    hook: 'If your team still runs manually, you are already late.',
    script_text: 'Owners are wasting hours on manual follow-up.',
    caption: 'AI is not optional anymore.',
    media_prompt: 'If your team still runs manually, you are already late.',
    media_url: 'https://huggingface.co/generated/video-asset.mp4',
    is_video: true,
    status: 'scheduled',
    publish_at: '2026-06-23T12:00:00.000Z',
    approval_required: true,
  }],
});

const filterDueItems = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Filter Due Items',
    position: [820, 420],
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: "const now = $now.toMillis();\nreturn $input.all().filter((item) => {\n  const row = item.json;\n  const statusOk = ['scheduled', 'ready'].includes(String(row.status ?? '').toLowerCase());\n  const approvalOk = row.approval_required !== true;\n  const publishAt = row.publish_at ? Date.parse(row.publish_at) : now;\n  return statusOk && approvalOk && publishAt <= now;\n}).map((item) => ({ json: item.json }));",
    },
  },
  output: [{
    content_id: 'content-x-1',
    platform: 'x',
    title: 'Why AI is mandatory now',
    caption: 'AI is now a mandatory operating system.',
    media_url: '',
    is_video: false,
    status: 'scheduled',
    publish_at: '2026-06-23T12:00:00.000Z',
    approval_required: false,
  }],
});

const loopDueItems = splitInBatches({
  version: 3,
  config: {
    name: 'Loop Due Items',
    position: [1120, 420],
    parameters: {
      batchSize: 1,
    },
  },
  output: [{
    content_id: 'content-x-1',
    platform: 'x',
    title: 'Why AI is mandatory now',
    caption: 'AI is now a mandatory operating system.',
    media_url: '',
    is_video: false,
    status: 'scheduled',
    publish_at: '2026-06-23T12:00:00.000Z',
    approval_required: false,
  }],
});

const routePlatform = switchCase({
  version: 3.4,
  config: {
    name: 'Route Platform',
    position: [1420, 420],
    parameters: {
      mode: 'rules',
      rules: {
        values: [
          {
            outputKey: 'instagram',
            conditions: {
              options: { caseSensitive: false, leftValue: '', typeValidation: 'strict' },
              conditions: [{ leftValue: expr('{{ $json.platform }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'instagram' }],
              combinator: 'and',
            },
          },
          {
            outputKey: 'facebook',
            conditions: {
              options: { caseSensitive: false, leftValue: '', typeValidation: 'strict' },
              conditions: [{ leftValue: expr('{{ $json.platform }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'facebook' }],
              combinator: 'and',
            },
          },
          {
            outputKey: 'x',
            conditions: {
              options: { caseSensitive: false, leftValue: '', typeValidation: 'strict' },
              conditions: [{ leftValue: expr('{{ $json.platform }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'x' }],
              combinator: 'and',
            },
          },
        ],
      },
      options: {
        fallbackOutput: 'none',
      },
    },
  },
});

const isInstagramVideo = ifElse({
  version: 2.3,
  config: {
    name: 'Is Instagram Video?',
    position: [1720, 240],
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: expr('{{ $json.is_video }}'), operator: { type: 'boolean', operation: 'true' }, rightValue: true }],
        combinator: 'and',
      },
    },
  },
});

const createInstagramImageContainer = node({
  type: 'n8n-nodes-base.facebookGraphApi',
  version: 1,
  config: {
    name: 'Create Instagram Image Container',
    position: [2020, 180],
    parameters: {
      authType: 'accessToken',
      hostUrl: 'graph.facebook.com',
      httpRequestMethod: 'POST',
      graphApiVersion: 'v25.0',
      node: 'YOUR_INSTAGRAM_BUSINESS_ID',
      edge: 'media',
      options: {
        queryParameters: {
          parameter: [
            { name: 'image_url', value: expr('{{ $json.media_url }}') },
            { name: 'caption', value: expr('{{ $json.caption }}') },
          ],
        },
      },
    },
    credentials: {
      facebookGraphApi: newCredential('Meta Page Token'),
    },
  },
  output: [{ id: '17890000000000000' }],
});

const createInstagramVideoContainer = node({
  type: 'n8n-nodes-base.facebookGraphApi',
  version: 1,
  config: {
    name: 'Create Instagram Video Container',
    position: [2020, 300],
    parameters: {
      authType: 'accessToken',
      hostUrl: 'graph.facebook.com',
      httpRequestMethod: 'POST',
      graphApiVersion: 'v25.0',
      node: 'YOUR_INSTAGRAM_BUSINESS_ID',
      edge: 'media',
      options: {
        queryParameters: {
          parameter: [
            { name: 'media_type', value: 'REELS' },
            { name: 'video_url', value: expr('{{ $json.media_url }}') },
            { name: 'caption', value: expr('{{ $json.caption }}') },
          ],
        },
      },
    },
    credentials: {
      facebookGraphApi: newCredential('Meta Page Token'),
    },
  },
  output: [{ id: '17890000000000001' }],
});

const publishInstagramMedia = node({
  type: 'n8n-nodes-base.facebookGraphApi',
  version: 1,
  config: {
    name: 'Publish Instagram Media',
    position: [2320, 240],
    parameters: {
      authType: 'accessToken',
      hostUrl: 'graph.facebook.com',
      httpRequestMethod: 'POST',
      graphApiVersion: 'v25.0',
      node: 'YOUR_INSTAGRAM_BUSINESS_ID',
      edge: 'media_publish',
      options: {
        queryParameters: {
          parameter: [
            { name: 'creation_id', value: expr('{{ $json.id }}') },
          ],
        },
      },
    },
    credentials: {
      facebookGraphApi: newCredential('Meta Page Token'),
    },
  },
  output: [{ id: '17900000000000000' }],
});

const isFacebookVideo = ifElse({
  version: 2.3,
  config: {
    name: 'Is Facebook Video?',
    position: [1720, 520],
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: expr('{{ $json.is_video }}'), operator: { type: 'boolean', operation: 'true' }, rightValue: true }],
        combinator: 'and',
      },
    },
  },
});

const publishFacebookImage = node({
  type: 'n8n-nodes-base.facebookGraphApi',
  version: 1,
  config: {
    name: 'Publish Facebook Image',
    position: [2020, 460],
    parameters: {
      authType: 'accessToken',
      hostUrl: 'graph.facebook.com',
      httpRequestMethod: 'POST',
      graphApiVersion: 'v25.0',
      node: 'YOUR_FACEBOOK_PAGE_ID',
      edge: 'photos',
      options: {
        queryParameters: {
          parameter: [
            { name: 'url', value: expr('{{ $json.media_url }}') },
            { name: 'caption', value: expr('{{ $json.caption }}') },
          ],
        },
      },
    },
    credentials: {
      facebookGraphApi: newCredential('Meta Page Token'),
    },
  },
  output: [{ id: 'fb-image-post-1' }],
});

const publishFacebookVideo = node({
  type: 'n8n-nodes-base.facebookGraphApi',
  version: 1,
  config: {
    name: 'Publish Facebook Video',
    position: [2020, 580],
    parameters: {
      authType: 'accessToken',
      hostUrl: 'graph-video.facebook.com',
      httpRequestMethod: 'POST',
      graphApiVersion: 'v25.0',
      node: 'YOUR_FACEBOOK_PAGE_ID',
      edge: 'videos',
      options: {
        queryParameters: {
          parameter: [
            { name: 'file_url', value: expr('{{ $json.media_url }}') },
            { name: 'description', value: expr('{{ $json.caption }}') },
            { name: 'title', value: expr('{{ $json.title }}') },
          ],
        },
      },
    },
    credentials: {
      facebookGraphApi: newCredential('Meta Page Token'),
    },
  },
  output: [{ id: 'fb-video-post-1' }],
});

const postToX = node({
  type: 'n8n-nodes-base.twitter',
  version: 2,
  config: {
    name: 'Post To X',
    position: [1720, 760],
    parameters: {
      resource: 'tweet',
      operation: 'create',
      text: expr('{{ ($json.title + "\\n\\n" + $json.caption).slice(0, 280) }}'),
    },
    credentials: {
      twitterOAuth2Api: newCredential('X OAuth2'),
    },
  },
  output: [{ id: 'x-post-1', text: 'AI is now a mandatory operating system.' }],
});

const markPosted = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Posted',
    position: [2620, 520],
    parameters: {
      resource: 'row',
      operation: 'upsert',
      dataTableId: {
        __rl: true,
        mode: 'id',
        value: '8PRuj7rfE2FDYkzR',
      },
      matchType: 'allConditions',
      filters: {
        conditions: [
          { keyName: 'content_id', condition: 'eq', keyValue: expr('{{ $("Loop Due Items").item.json.content_id }}') },
          { keyName: 'platform', condition: 'eq', keyValue: expr('{{ $("Loop Due Items").item.json.platform }}') },
        ],
      },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          content_id: expr('{{ $("Loop Due Items").item.json.content_id }}'),
          platform: expr('{{ $("Loop Due Items").item.json.platform }}'),
          title: expr('{{ $("Loop Due Items").item.json.title }}'),
          hook: expr('{{ $("Loop Due Items").item.json.hook }}'),
          script_text: expr('{{ $("Loop Due Items").item.json.script_text }}'),
          caption: expr('{{ $("Loop Due Items").item.json.caption }}'),
          media_prompt: expr('{{ $("Loop Due Items").item.json.media_prompt }}'),
          media_url: expr('{{ $("Loop Due Items").item.json.media_url }}'),
          is_video: expr('{{ $("Loop Due Items").item.json.is_video }}'),
          status: 'posted',
          publish_at: expr('{{ $("Loop Due Items").item.json.publish_at }}'),
          approval_required: expr('{{ $("Loop Due Items").item.json.approval_required }}'),
        },
      },
    },
  },
  output: [{
    content_id: 'content-x-1',
    platform: 'x',
    status: 'posted',
  }],
});

export default workflow('virel-social-publisher', 'Virel - Social Publisher')
  .add(publishTrigger)
  .to(loadQueue)
  .to(filterDueItems)
  .to(loopDueItems
    .onEachBatch(routePlatform
      .onCase(0, isInstagramVideo
        .onTrue(createInstagramVideoContainer.to(publishInstagramMedia).to(nextBatch(loopDueItems)))
        .onFalse(createInstagramImageContainer.to(publishInstagramMedia).to(nextBatch(loopDueItems))))
      .onCase(1, isFacebookVideo
        .onTrue(publishFacebookVideo.to(nextBatch(loopDueItems)))
        .onFalse(publishFacebookImage.to(nextBatch(loopDueItems))))
      .onCase(2, postToX.to(nextBatch(loopDueItems))))
  )
  .add(publishInstagramMedia.to(markPosted))
  .add(publishFacebookImage.to(markPosted))
  .add(publishFacebookVideo.to(markPosted))
  .add(postToX.to(markPosted));
