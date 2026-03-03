import { PrismaClient } from '@prisma/client'
import { existsSync } from 'node:fs'
import path from 'node:path'

// Default to a Prisma-compatible local DB using an absolute path to avoid cwd ambiguity.
const dbCandidates = [path.resolve(process.cwd(), 'db/custom.db'), path.resolve(process.cwd(), 'prisma/dev.db')]
const defaultDbPath = dbCandidates.find((candidate) => existsSync(candidate)) ?? dbCandidates[0]
const defaultDatabaseUrl = `file:${defaultDbPath}`
const isProduction = process.env.NODE_ENV === 'production'
const isBuildPhase =
  process.env.NEXT_PHASE === 'phase-production-build' ||
  process.env.npm_lifecycle_event === 'build'
const isProductionRuntime = isProduction && !isBuildPhase

if (isProductionRuntime && !process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL is not set. Configure it in environment for production runtime')
}

const databaseUrl = process.env.DATABASE_URL ?? defaultDatabaseUrl

if (!process.env.DATABASE_URL) {
  console.warn(`DATABASE_URL is not set. Using default SQLite path ${defaultDbPath}`)
}

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const db =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['query'] : [],
    datasources: {
      db: { url: databaseUrl },
    },
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db
