import { expect, test, describe } from "bun:test";
import { appInfoSchema, dynamicComposeSchema } from '@runtipi/common/schemas'
import { fromError } from 'zod-validation-error';
import fs from 'node:fs'
import path from 'node:path'
import { type } from "arktype";

const getApps = async () => {
  const appsDir = await fs.promises.readdir(path.join(process.cwd(), 'apps'))

  const appDirs = appsDir.filter((app) => {
    const stat = fs.statSync(path.join(process.cwd(), 'apps', app))
    return stat.isDirectory()
  })

  return appDirs
};

const getFile = async (app: string, file: string) => {
  const filePath = path.join(process.cwd(), 'apps', app, file)
  try {
    const file = await fs.promises.readFile(filePath, 'utf-8')
    return file
  } catch (err) {
    return null
  }
}

describe("each app should have the required files", async () => {
  const apps = await getApps()

  for (const app of apps) {
    const files = ['config.json', 'docker-compose.yml', 'metadata/logo.jpg', 'metadata/description.md']

    for (const file of files) {
      test(`app ${app} should have ${file}`, async () => {
        const fileContent = await getFile(app, file)
        expect(fileContent).not.toBeNull()
      })
    }
  }
})

describe("each app should have a valid config.json", async () => {
  const apps = await getApps()

  for (const app of apps) {
    test(`app ${app} should have a valid config.json`, async () => {
      const fileContent = await getFile(app, 'config.json')
      const parsed = appInfoSchema.omit('urn')(JSON.parse(fileContent || '{}'))

      if (parsed instanceof type.errors) {
        const validationError = fromError(parsed);
        console.error(`Error parsing config.json for app ${app}:`, validationError.toString());
      }

      expect(parsed instanceof type.errors).toBe(false)
    })
  }
})

describe("each app should have a valid docker-compose.yml", async () => {
  const apps = await getApps()

  for (const app of apps) {
    test(`app ${app} should have a valid docker-compose.yml`, async () => {
      const fileContent = await getFile(app, 'docker-compose.yml')
      expect(fileContent).not.toBeNull()

      const compose = Bun.YAML.parse(fileContent || '') as any

      // Top-level Runtipi extension
      expect(compose?.['x-runtipi']?.schema_version).toBe(2)

      // At least one service
      const services = Object.entries(compose?.services ?? {}) as [string, any][]
      expect(services.length).toBeGreaterThan(0)

      // Every service needs an image
      for (const [name, service] of services) {
        if (!service?.image) console.error(`Service ${name} in app ${app} has no image`)
        expect(service?.image).toBeTruthy()
      }

      // Exactly one main service with an internal port
      const mainServices = services.filter(([, s]) => s?.['x-runtipi']?.is_main === true)
      expect(mainServices.length).toBe(1)
      expect(mainServices[0][1]['x-runtipi'].internal_port).toBeDefined()
    })
  }
});
