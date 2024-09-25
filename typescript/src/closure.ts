import * as inspector from 'node:inspector/promises'
export type BreakpointHitEvent = inspector.InspectorNotification<inspector.Debugger.PausedEventDataType>
import * as logging from './_logger'

const logger = logging.getLogger('closure')

const getNextPausedEvent = (session: inspector.Session): Promise<BreakpointHitEvent> =>
  new Promise((resolve, reject) => {
    session.once('Debugger.paused', (params) => {
      console.log('paused', JSON.stringify(params, null, 2))
      resolve(params)
    })
  })
const handleBreakpointHit = async (session: inspector.Session, { params }: BreakpointHitEvent) => {
  let variableValues: Record<string, any> = {}
  const { callFrames } = params
  const scopes = callFrames[0].scopeChain

  // Get the variables you're interested in
  for (const scope of scopes) {
    if (scope.type === 'closure') {
      const result = await session
        .post('Runtime.getProperties', {
          objectId: scope.object.objectId,
          ownProperties: false,
          accessorPropertiesOnly: false,
          generatePreview: false,
        })
        .catch((err) => {
          logger.error('Failed to get properties', err)
          return null
        })
      if (!result) {
        continue
      }
      for (const prop of result.result) {
        if (prop.value && prop.value.value !== undefined) {
          variableValues[prop.name] = prop.value.value
        }
      }
    }
  }
  return variableValues
}

// this only works for inline source maps. it looks like ts-node always gives those to node
// regardless of what the tsconfig says?
export function extractSourceMapUrl(fileContent: string) {
  const sourceMapRegex = /\/\/[#@]\s*sourceMappingURL=(.+)$/m
  const match = fileContent.match(sourceMapRegex)
  if (match) {
    if (match[1].indexOf('base64,') > -1) {
      return match[1].split('base64,')[1]
    }
    return match[1]
  }
  return null
}
export function getSourceMapJSON(base64SourceMap: string) {
  try {
    const sourceMapContent = Buffer.from(base64SourceMap, 'base64').toString()
    return JSON.parse(sourceMapContent)
  } catch (e) {
    logger.error('Error parsing source map', { err: e })
    return null
  }
}

export async function resolveScriptIdToFile(session: inspector.Session, scriptId: string) {
  try {
    const result = await session.post('Debugger.getScriptSource', { scriptId })
    logger.debug('Script source', { result })
    return result
  } catch (err) {
    logger.error(`Error resolving scriptId ${scriptId}:`, { err })
    return 
  }
}

export async function resolveMultipleScriptIds(session: inspector.Session, scriptIds: string[]) {
  const results = []
  for (const scriptId of scriptIds) {
    try {
      const result = await resolveScriptIdToFile(session, scriptId)
      results.push(result)
    } catch (error) {
      logger.error(`Error resolving scriptId ${scriptId}:`, { error })
      results.push({ scriptId, filePath: 'Error: ' + (error as Error).message })
    }
  }
  return results
}
