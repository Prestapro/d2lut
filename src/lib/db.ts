import { PrismaClient } from '@prisma/client'

const defaultDatabaseUrl = 'file:./data/cache/d2lut.db'
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
  console.warn(`DATABASE_URL is not set. Using default SQLite path ${defaultDatabaseUrl}`)
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
