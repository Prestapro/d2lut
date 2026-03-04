-- CreateTable
CREATE TABLE "D2Item" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "variantKey" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "displayName" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "d2rCode" TEXT,
    "subCategory" TEXT,
    "description" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "PriceEstimate" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "itemId" TEXT NOT NULL,
    "priceFg" REAL NOT NULL,
    "confidence" TEXT NOT NULL,
    "nObservations" INTEGER NOT NULL DEFAULT 0,
    "minPrice" REAL,
    "maxPrice" REAL,
    "avgPrice" REAL,
    "priceChange" REAL,
    "lastUpdated" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PriceEstimate_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "D2Item" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PriceObservation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "itemId" TEXT NOT NULL,
    "estimateId" TEXT,
    "priceFg" REAL NOT NULL,
    "confidence" REAL NOT NULL,
    "signalKind" TEXT NOT NULL,
    "source" TEXT,
    "sourceId" TEXT,
    "author" TEXT,
    "observedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PriceObservation_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "D2Item" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "PriceObservation_estimateId_fkey" FOREIGN KEY ("estimateId") REFERENCES "PriceEstimate" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "FilterPreset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "showTrash" BOOLEAN NOT NULL DEFAULT false,
    "showPrices" BOOLEAN NOT NULL DEFAULT true,
    "showColors" BOOLEAN NOT NULL DEFAULT true,
    "showBases" BOOLEAN NOT NULL DEFAULT true,
    "priceThreshold" REAL NOT NULL DEFAULT 0,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "FilterItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "presetId" TEXT NOT NULL,
    "itemId" TEXT NOT NULL,
    "customThreshold" REAL,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "FilterItem_presetId_fkey" FOREIGN KEY ("presetId") REFERENCES "FilterPreset" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "FilterItem_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "D2Item" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "D2Item_variantKey_key" ON "D2Item"("variantKey");

-- CreateIndex
CREATE INDEX "D2Item_category_idx" ON "D2Item"("category");

-- CreateIndex
CREATE UNIQUE INDEX "PriceEstimate_itemId_key" ON "PriceEstimate"("itemId");

-- CreateIndex
CREATE INDEX "PriceEstimate_priceFg_idx" ON "PriceEstimate"("priceFg");

-- CreateIndex
CREATE INDEX "PriceObservation_itemId_observedAt_idx" ON "PriceObservation"("itemId", "observedAt");

-- CreateIndex
CREATE UNIQUE INDEX "FilterPreset_name_key" ON "FilterPreset"("name");

-- CreateIndex
CREATE UNIQUE INDEX "FilterItem_presetId_itemId_key" ON "FilterItem"("presetId", "itemId");
