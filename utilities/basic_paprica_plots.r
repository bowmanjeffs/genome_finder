## Don't forget to set your working directory.

setwd('your/working/directory')

library(data.table)

## Define the prefix of your input files.  This is whatever you set the -o flag
## to when you ran paprica-combine_results.py.

prefix <- '20240412_orca_basin'

#### Define some functions to read in the paprica output ####

read.edge <- function(prefix, domain){
    tally <- fread(paste0(prefix, '.', domain, '.edge_tally.csv'), header = T, sep = ',', data.table = F)
    row.names(tally) <- tally$V1
    tally$V1 <- NULL
    tally <- tally[order(row.names(tally)),]
    tally[is.na(tally)] <- 0
    return(tally)
}

read.unique <- function(prefix, domain){
    unique <- fread(paste0(prefix, '.', domain, '.unique_tally.csv'), header = T, sep = ',', data.table = F)
    row.names(unique) <- unique$V1
    unique$V1 <- NULL
    unique <- unique[sort(row.names(unique)),]
    unique[is.na(unique)] <- 0
    return(unique)
}

read.map <- function(prefix, domain){
    map <- read.csv(paste0(prefix, '.', domain, '.seq_edge_map.csv'), header = T, row.names = 1)
    return(map)
}

read.taxa <- function(prefix, domain){
    taxa <- read.csv(paste0(prefix, '.', domain, '.taxon_map.csv'), header = T, row.names = 1, sep = ',', as.is = T)
    return(taxa)
}

read.data <- function(prefix, domain){
    data <- read.csv(paste0(prefix, '.', domain, '.edge_data.csv'), header = T, row.names = 1)
    return(data)
}

#### read data files and prepare for analysis ####

tally.bac <- read.edge(prefix, 'bacteria')
tally.arc <- read.edge(prefix, 'archaea')
tally.euk <- read.edge(prefix, 'eukarya')

unique.bac <- read.unique(prefix, 'bacteria')
unique.arc <- read.unique(prefix, 'archaea')
unique.euk <- read.unique(prefix, 'eukarya')

data.bac <- read.data(prefix, 'bacteria')
data.arc <- read.data(prefix, 'archaea')

taxa.bac <- read.taxa(prefix, 'bacteria')
taxa.arc <- read.taxa(prefix, 'archaea')
taxa.euk <- read.taxa(prefix, 'eukarya')

map.bac <- read.map(prefix, 'bacteria')
map.arc <- read.map(prefix, 'archaea')
map.euk <- read.map(prefix, 'eukarya')

## Save these objects as R data files. This makes loading them in the future
## virtually instantaneous.

save(list = c('unique.bac',
              'unique.arc',
              'data.bac',
              'data.arc',
              'taxa.bac',
              'taxa.arc',
              'map.bac',
              'map.arc',
              'tally.bac',
              'tally.arc'), file = paste0(prefix, '.Rdata'))

## Now, when you return to this script you can just skip to here after defining
## the prefix character string.

load(paste0(prefix, '.Rdata'))

## Join the bacteria and archaea datasets. This presumes you're using a cross-domain
## primer and it therefor makes sense to analyze these data together.

unique <- merge(unique.bac, unique.arc, by = 0, all = T)
tally <- merge(tally.bac, tally.arc, by = 0, all = T)

row.names(unique) <- unique$Row.names
row.names(tally) <- tally$Row.names

unique$Row.names <- NULL
tally$Row.names <- NULL

## convert NAs to 0

unique[is.na(unique)] <- 0
tally[is.na(tally)] <- 0

## Eliminate libraries below size threshold.  You should
## pick something that works for your sample set.  In practice
## we try to avoid libraries with fewer than 5000 reads.

tally.select <- tally[rowSums(tally) > 3000,]
unique.select <- unique[rowSums(unique) > 3000,]

## OPTIONAL. Drop a specific library or libraries, such as a library
## that you know is bad or have some reason for not wanting to analyze further.

unique.select <- unique.select[grep('SRR14129902.16S.exp.', row.names(unique.select), invert = T),]
tally.select <- tally.select[grep('SRR14129902.16S.exp.', row.names(tally.select), invert = T),]

## If you dropped any libraries, you probably want this reflected in your
## sample data file as well.

data.bac.select <- data.bac[row.names(unique.select),]
data.arc.select <- data.arc[row.names(unique.select),]

## Eliminate ASVs below a certain abundance threshold. In general you should
## at least get rid of everything of abundance = 1, which greatly reduces the
## size of your data frame. Typically we set the threshold at 10.

unique.select <- unique.select[,colSums(unique.select) > 1]

## Drop any problematic taxa, for example, that you think are mitochondria or chloroplasts.

drop.asvs.by.taxa <- function(map, taxa, target_taxa, rank){
  keep.edges <- row.names(taxa)[which(taxa[,rank] != target_taxa)]
  keep.asvs <- row.names(map)[which(map$global_edge_num %in% keep.edges)]
  selected <- unique.select[,which(colnames(unique.select) %in% keep.asvs)]
  return(selected)
}

unique.select <- drop.asvs.by.taxa(map.bac, taxa.bac, 'Candidatus Nasuia deltocephalinicola', 'taxon')
unique.select <- drop.asvs.by.taxa(map.bac, taxa.bac, 'Candidatus Carsonella ruddii', 'taxon')

## Subsample to the size of your smallest library.  The alternative is to move
## to relative abundance, but that gets weird if you want to apply a log
## normalization later on.

unique.select.ra <- unique.select/rowSums(unique.select) # relative abundance
unique.select.sub <- unique.select
sub.size <- floor(min(rowSums(unique.select)))

for(row in 1:length(row.names(unique.select.ra))){
    temp <- table(sample(colnames(unique.select), size = sub.size, replace = T, prob = unique.select.ra[row,]))
    temp <- as.data.frame(temp)
    row.names(temp) <- temp$Var1
    temp$Var1 <- NULL
    unique.select.sub[row,row.names(temp)] <- temp[row.names(temp), 'Freq']
}

## Normalize. We find that a typical log10 normalization often works fine
## for community structure data, but of course this is data and analysis
## dependent.

unique.select.log10 <- log10(unique.select.sub)
unique.select.log10[unique.select.log10 < 0] <- 0
unique.select.log10 <- unique.select.log10/rowSums(unique.select.log10)

## get taxonomy for ASVs

get.names <- function(domain, map, taxa){
    unique.lab.Row <- map[colnames(unique.select), 'global_edge_num']
    unique.lab.Row <- taxa[unique.lab.Row, 'taxon']
    unique.lab.Row[unique.lab.Row == ""] <- domain
    unique.lab.Row[is.na(unique.lab.Row)] <- domain
    return(unique.lab.Row)
}

lab.row.bac <- get.names('bacteria', map.bac, taxa.bac)
lab.row.arc <- get.names('archaea', map.arc, taxa.arc)
lab.row.euk <- get.names('eukarya', map.euk, taxa.euk)
lab.row <- cbind(lab.row.bac, lab.row.arc)

#### make a heatmap of ASV abundance ####

## OPTIONAL: Select a specific taxonomy

get.asvindex.by.taxa <- function(map, taxa, target_taxa, rank){
  target.edges <- row.names(taxa)[which(taxa[,rank] == target_taxa)]
  target.asvs <- row.names(map)[which(map$global_edge_num %in% target.edges)]
  selected <- which(colnames(unique.select) %in% target.asvs)
  return(selected)
}

selected <- get.asvindex.by.taxa(map.bac, taxa.bac, 'Cyanobacteria', 'phylum')

## Alternatively restrict to top 50:

selected <- order(colSums(unique.select.log10), decreasing = T)[1:50]

heat.col <- colorRampPalette(c('white', 'lightgoldenrod1', 'darkgreen'))(100)

library(gplots)

heatmap.2(t(data.matrix(unique.select.log10[,selected])),
          trace = 'none',
          #Colv = NA,
          scale = NULL,
          col = heat.col,
          labRow = lab.row[selected],
          margins = c(10, 10))

#### NMDS plot ####

library(vegan)
library(oce)

unique.mds <- metaMDS(unique.select.log10, k = 3)

mds.samples <- unique.mds$points

## Color points according to potential community growth rate.

point.cols <- terrain.colors(length(mds.samples[,1]))[as.numeric(cut(data.bac.select$gRodon.d.mean,breaks = length(mds.samples[,1])))]

plot(mds.samples[,1], mds.samples[,2],
     ylab = 'Dim 2',
     xlab = 'Dim 1',
     pch = 19,
     col = point.cols,
     cex = 2)

### which taxa drive variation in MDS plot? ###

scaling.factor <- 0.5 # data dependent

mds.species <- unique.mds$species

## Select top 50 contributors to first dimension.

target.asv <- row.names(mds.species)[order(abs(mds.species[,'MDS1']), decreasing = T)[1:50]]
target.clade <- map.bac[target.asv, 'global_edge_num']
target.taxa <- taxa.bac[target.clade, 'taxon']

arrows(0,0,
      (mds.species[target.asv,'MDS1'] * scaling.factor),
       (mds.species[target.asv,'MDS2'] * scaling.factor))
