#!/usr/bin/env python3
# -*- coding: utf-8 -*-

help_string = """
Created on Sun Jan 31 13:13:09 2016

@author: Jeff Bowman, bowmanjs@ldeo.columbia.edu

paprica is licensed under a Creative Commons Attribution-NonCommercial
4.0 International License.  IF you use any portion of paprica in your
work please cite:

Bowman, Jeff S., and Hugh W. Ducklow. "Microbial Communities Can Be Described
by Metabolic Structure: A General Framework and Application to a Seasonally
Variable, Depth-Stratified Microbial Community from the Coastal West Antarctic
Peninsula." PloS one 10.8 (2015): e0135868.

If your analysis makes specific use of pplacer, Infernal, DIAMOND, or pathway-tools
please make sure that you also cite the relevant publications.

This script identifies all the features in the Genbank files of completed
genomes that have an EC number and are thus useful for pathway prediction.  It
creates a nonredundant fasta of these sequences and a database of all the
feature qualifiers that are necessary to build Genbank files containing the
features "on the fly".

This script uses DIAMOND to create a database of the nonredundant fasta against
which query shotgun MG sequences reads can be searched.

CALL AS:
    paprica-mgt_build.py [options]
    
OPTIONS:
-ref_dir: The name of the directory containing the paprica database.  Not necessary
if your database is named ref_genome_database (the default).

"""

executable = '/bin/bash' # shell for executing commands

import os
import shutil
import subprocess
import sys
from joblib import Parallel, delayed
import gzip
import urllib

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
from Bio import SeqFeature

import pandas as pd
import numpy as np

#%% Function definitions.

## Define a stop function for troubleshooting.

def stop_here():
    stop = []
    print('Manually stopped!')
    print(stop[1])
    
## Define a function to download viral genomes.
    
def download_assembly(ref_dir_domain, executable, assembly_accession):
    try:
        strain_ftp = genome_data_virus.loc[assembly_accession, 'ftp_path']
        
        ## Required to use proxy server on SIO network.  Bafflingly there is bug in wget that
        ## disallows the use of a wildcard with ftp when a proxy server is used.  So ftp
        ## path must be converted to http.  Note that this requires the use of the -nd flag
        ## because the http protocol will try to create the entire directory structure (grr!)
        
        base_name = strain_ftp.split('/')[-1]

        mkdir = subprocess.Popen('mkdir ' + ref_dir_domain + 'refseq/' + assembly_accession, shell = True, executable = executable)
        mkdir.communicate()
        
        for extension in ['_genomic.fna.gz', '_genomic.gbff.gz', '_protein.faa.gz']:
            wget0 = subprocess.Popen('cd ' + ref_dir_domain + 'refseq/' + assembly_accession + ';wget \
                                     --tries=10 -N -q -r -nd -T30 -e robots=off ' \
                                     + strain_ftp + '/' + base_name + extension, \
                                     shell = True, executable = executable)
            wget0.communicate() 
        
        gunzip = subprocess.Popen('gunzip ' + ref_dir_domain + 'refseq/' + assembly_accession + '/*', shell = True, executable = executable)
        gunzip.communicate()
        
        print(assembly_accession + ':' + strain_ftp)
        
    except KeyError:
        print('no', assembly_accession, 'path')
        
## Define a function to get the MMETS info for euk transcriptomes.
        
def get_eukaryotes():

    ## Get eukaryote sample data from MMETSP.
        
    if 'sample-attr.tab' not in os.listdir(ref_dir_domain):
        subprocess.call('cd ' + ref_dir_domain + ';wget --tries=10 -T30 -q https://de.cyverse.org/anon-files//iplant/home/shared/imicrobe/projects/104/sample-attr.tab', shell = True, executable = executable)
    
    ## Parse this file into a dataframe.
            
    summary_complete = pd.DataFrame()
    l = 0    
    
    with open(ref_dir_domain + 'sample-attr.tab', 'r') as sample_attr:
        for line in sample_attr:
            line = line.rstrip()
            line = line.split('\t')
            l = l + 1
            if l != 1:
                summary_complete.loc[line[0], 'sample_name'] = line[1]
                summary_complete.loc[line[0], line[2]] = line[3]   
                            
    return(summary_complete)  
        
## Define a function to download MMETSP transcriptomes.
        
def download_euks(online_directory):
    
    os.makedirs(ref_dir_domain + 'refseq', exist_ok = True)
    
    try:
        assembly_accession = euk_summary_complete.loc[online_directory, 'sample_name']
        strain_ftp = 'https://de.cyverse.org/anon-files//iplant/home/shared/imicrobe/projects/104/samples/' + online_directory
        
        strain_nt = assembly_accession + '.nt.fa'
        strain_fa = assembly_accession + '.pep.fa'
        
        os.makedirs(ref_dir_domain + 'refseq/' + assembly_accession, exist_ok = True)
        
        for f in [strain_nt, strain_fa]:
            subprocess.call('cd ' + ref_dir_domain + 'refseq/' + assembly_accession + ';wget --tries=10 -N -q -r -nd -T30 -e robots=off ' + strain_ftp + '/' + f, shell = True, executable = executable)
        
        subprocess.call('cd ' + ref_dir_domain + 'refseq/' + assembly_accession + ';wget --tries=10 -N -q -r -nd -T30 -e robots=off ' + strain_ftp + '/annot/swissprot.gff3', shell = True, executable = executable)
        
        print(assembly_accession + ':' + ref_dir_domain + 'refseq/' + assembly_accession)
        
    except KeyError:
        print('no', online_directory, 'online directory') 
        
def create_euk_files(d):
    
    ## First create a df mapping protein id to SwissProt accession number.
    
    columns = ['prot_id', 'swissprot', 'description']
    spt = pd.read_csv(ref_dir_domain + 'refseq/' + d + '/swissprot.gff3', index_col = 0, comment = '#', names = columns, usecols = [0,8,10], sep = ';|\t', engine = 'python')
    spt['swissprot'] = spt['swissprot'].str.replace('Name=Swiss-Prot:', '')
    spt['description'] = spt['description'].str.replace('Description=Swiss-Prot:', '')
    
    ## Create empty list to hold gene features pulled from cds.fa.
    
    features = []
    
    ## Artificial start, stops are needed.
    
    combined_length = 1
    
    print('generating genbank format files for', d + '...')
    
    ## Some directory names differ from the accession number.  Rename these
    ## directories to match the accession number.
    
    for f in os.listdir(ref_dir_domain + 'refseq/' + d):
        if f.endswith('.pep.fa'):
            a = f.split('.pep.fa')[0]
            
    if a != d:
        os.rename(ref_dir_domain + 'refseq/' + d, ref_dir_domain + 'refseq/' + a)
        print('directory', d, 'is now', a)
    
    for record in SeqIO.parse(ref_dir_domain + 'refseq/' + a + '/' + a + '.pep.fa', 'fasta'):
            
        ## The swissprot annotations are indexed by MMETSP record locator, not
        ## by the actual record.id.
        
        sprot_name = str(record.description).split('NCGR_PEP_ID=')[1]
        sprot_name = sprot_name.split(' /')[0]
        	
        try:
            temp_spt = spt.loc[sprot_name, 'swissprot']
        except KeyError:
            continue
        		
        temp_sprot = sprot_df[sprot_df.index.isin(list(temp_spt))]
        	
        ecs = list(set(temp_sprot.ec))
        descriptions = list(set(temp_sprot.name))
        	
        ## Embed all information necessary to create the Genbank file as qualifiers, then
        ## append to this list of records for that genome.
        	
        qualifiers = {'protein_id':sprot_name, 'locus_tag':str(record.id), 'EC_number':ecs, 'product':descriptions, 'translation':str(record.seq)}
        new_feature = SeqFeature.SeqFeature(type = 'CDS', qualifiers = qualifiers)
        new_feature.location = SeqFeature.FeatureLocation(combined_length, combined_length + len(str(record.seq)))
        features.append(new_feature)
        
        combined_length = combined_length + len(str(record.seq))
        
    ## Write the records in Genbank format.  Even though you will ultimately
    ## want to use the gbk extension, to match the (silly) Genbank convention
    ## use gbff.
        
    new_record = SeqRecord(Seq('nnnn'), id = a, name = a, features = features)
    new_record.annotations['molecule_type']	= 'DNA'
    SeqIO.write(new_record, open(ref_dir_domain + 'refseq/' + a + '/' + a + '.gbff', 'w'), 'genbank')

#%% Read in command line arguments.

command_args = {}

for i,arg in enumerate(sys.argv):
    if arg.startswith('-'):
        arg = arg.strip('-')
        try:
            command_args[arg] = sys.argv[i + 1]
        except IndexError:
            command_args[arg] = ''
        
if 'h' in list(command_args.keys()):
    print(help_string)
    quit()

try:
    ref_dir = command_args['ref_dir']
except KeyError:
    ref_dir = 'ref_genome_database'
    
if ref_dir.endswith('/') == False:
    ref_dir = ref_dir + '/'

paprica_path = os.path.dirname(os.path.realpath("__file__")) + '/' # The location of the actual paprica scripts.  
ref_dir = paprica_path + ref_dir

#%% Download euk transcriptomes.

ref_dir_domain = ref_dir + 'eukarya/'

euk_summary_complete = get_eukaryotes()

## Execute the download function.  You can't do this from inside the function
## because parallel requires input variables to be global.
 
Parallel(n_jobs = -1, verbose = 5)(delayed(download_euks)
(online_directory) for online_directory in euk_summary_complete.index)
    
## Check to make sure that each downloaded directory has a .fa, .nt, and .gff3 file
## extension.  Remove if it does not, and add to bad_eukarya.
    
bad_eukarya = []
    
for genome in euk_summary_complete.sample_name:
    file_count = 0
    
    try:
        for f in os.listdir(ref_dir_domain + 'refseq/' + genome):
            if f.endswith('pep.fa'):
                file_count = file_count + 1
            if f.endswith('nt.fa'):
                file_count = file_count + 1
            elif f.endswith('swissprot.gff3'):
                file_count = file_count + 1 
    except OSError:
        pass
            
    if file_count != 3:
        try:
            shutil.rmtree(ref_dir_domain + 'refseq/' + genome)
        except OSError:
            pass
        bad_eukarya.append(genome)
    
## Remove incomplete downloads from summary_complete.
    
euk_summary_complete = euk_summary_complete[~euk_summary_complete.sample_name.isin(bad_eukarya)]

## For Eukarya, dataframe is currently indexed by online directory number.
## Downstream scripts need it to be indexed by acccession.  

euk_summary_complete = euk_summary_complete.set_index('sample_name')
euk_summary_complete.to_csv(ref_dir_domain + 'genome_data.final.csv') 

## Create gbff files for eukarya.  Start by downloading enzyme.dat.

print('Downloading enzyme.dat from ftp.expasy.org...')

enzyme = urllib.request.urlopen('ftp://ftp.expasy.org/databases/enzyme/enzyme.dat').read()
enzyme_file = open(ref_dir_domain + 'enzyme.dat', 'wb')
enzyme_file.write(enzyme)
enzyme_file.close()

with open('enzyme_table.dat', 'w') as enzyme_out, open(ref_dir_domain + 'enzyme.dat', 'r') as enzyme:
    print('accession', 'ec', 'name', file = enzyme_out)
    print('Parsing enzyme.dat to enzyme_table.dat...')
    for line in enzyme:
        if line.startswith('ID'):
            ec = line.split()[1]
            ec = ec.rstrip()
            
        if line.startswith('DE'):
            name = line.split()[1]
            name = name.rstrip()
            
        if line.startswith('DR'):
            line = line.strip('DR')
            line = line.strip()
            line = line.rstrip()
            line = line.rstrip(';')
            line = line.split(';')
            
            for sprot in line:
                sprot = sprot.split(',')[0]
                sprot = sprot.strip()
                sprot = sprot.rstrip()
                
                print(sprot, ec, name, file=enzyme_out)

sprot_df = pd.read_csv('enzyme_table.dat', header = 0, index_col = 0, sep = ' ')

## Create gbff files.

Parallel(n_jobs = -1, verbose = 5)(delayed(create_euk_files)
(d) for d in euk_summary_complete.index)

#%% Download virus sequences, since they aren't used anywhere else.  Since this
## isn't a particularly large database, just overwrite existing.

try:
    shutil.rmtree(ref_dir + 'virus')
except OSError:
    pass

os.mkdir(ref_dir + 'virus')
os.mkdir(ref_dir + 'virus' + '/refseq')

genome_data_virus = pd.read_table('ftp://ftp.ncbi.nlm.nih.gov/genomes/refseq/viral/assembly_summary.txt', header = 1, index_col = 0)
genome_data_virus = genome_data_virus[genome_data_virus.assembly_level == 'Complete Genome']

Parallel(n_jobs = -1, verbose = 5)(delayed(download_assembly)
(ref_dir + 'virus/', executable, assembly_accession) for assembly_accession in genome_data_virus.index)

## Check to make sure critical files downloaded.

incomplete_genome = []
    
for assembly_accession in genome_data_virus.index:

    ng_file_count = 0
    temp_faa = ''
    
    ## Genbank now puts some useless fna files in the directory, remove
    ## or they complicate things.
    
    for f in os.listdir(ref_dir + 'virus/' + 'refseq/' + assembly_accession):
        if f.endswith('from_genomic.fna'):
            os.remove(ref_dir + 'virus/' + 'refseq/' + assembly_accession + '/' + f)
            
    ## Now check to make sure that the files you want are in place.
    
    for f in os.listdir(ref_dir + 'virus/' + 'refseq/' + assembly_accession):
        if f.endswith('protein.faa'):
            temp_faa = f
            ng_file_count = ng_file_count + 1
        elif f.endswith('genomic.fna'):
            ng_file_count = ng_file_count + 1
        elif f.endswith('genomic.gbff'):
            ng_file_count = ng_file_count + 1
                    
    if ng_file_count != 3:
        print(assembly_accession, 'is missing a Genbank file')
        incomplete_genome.append(assembly_accession)
                       
genome_data_virus = genome_data_virus.drop(incomplete_genome)
genome_data_virus['tax_name'] = genome_data_virus.organism_name.replace(' ', '_')
genome_data_virus.to_csv(ref_dir + 'virus/' + 'genome_data.final.csv')

#%%  Create database.

## Read in genome_data so that you can iterate by genomes that are actually
## used by paprica.

genome_data_bacteria = pd.read_csv(ref_dir + 'bacteria/genome_data.final.csv.gz', index_col = 0, header = 0)
genome_data_bacteria = genome_data_bacteria.dropna(subset = ['clade'])
genome_data_bacteria['domain'] = 'bacteria'

genome_data_archaea = pd.read_csv(ref_dir + 'archaea/genome_data.final.csv.gz', index_col = 0, header = 0)
genome_data_archaea = genome_data_archaea.dropna(subset = ['clade'])
genome_data_archaea['domain'] = 'archaea'

genome_data_eukarya = pd.read_csv(ref_dir + 'eukarya/genome_data.final.csv', index_col = 0, header = 0)
genome_data_eukarya['domain'] = 'eukarya'
genome_data_eukarya.drop_duplicates(subset = ['taxon_id'], inplace = True)

genome_data_virus = pd.read_csv(ref_dir + 'virus/genome_data.final.csv', index_col = 0, header = 0)
genome_data_virus['domain'] = 'virus'

### !!! below block is commented for now, not clear that this is necessary !!! ###

### For bacteria and archaea, limit resolution to species.  This is
### an effort to limit the number of CDS lost because they are not
### unique.
#
#genome_data_bacteria.drop_duplicates(subset = ['species_taxid'], inplace = True)
#genome_data_archaea.drop_duplicates(subset = ['species_taxid'], inplace = True)
#
### For eukarya, limit resolution to strain because there is no
### MMETSP equivalent for "species_taxid".
#
#genome_data_eukarya.drop_duplicates(subset = ['taxon_id'], inplace = True)

## Combine all domain databases.

genome_data = pd.concat([genome_data_bacteria, genome_data_archaea, genome_data_eukarya, genome_data_virus])

## Iterate through all the files in refseq and find the gbff files.  First pass
## just counts the number of features with EC_number so that we can create a
## Numpy array the right size.

def count_ec(output, i):
    
    d = genome_data.index[i]
    eci = 0
    domain = genome_data.loc[d, 'domain']
    
    for f in os.listdir(ref_dir + domain + '/refseq/' + d):
        if f.endswith('gbff'):
            
            try:
                for record in SeqIO.parse(ref_dir + domain + '/refseq/' + d + '/' + f, 'genbank'):
                    for feature in record.features:
                        if feature.type == 'CDS':
                            if 'EC_number' in list(feature.qualifiers.keys()):                              
                                eci = eci + 1
                
                output[i] = eci
                print(d, 'has', eci, 'features')

            ## For some assemblies an error is raised on a second(?) record identified
            ## in the Genbank file.  It isn't clear why this is happening, pass the error
            ## here.
                                
            except AttributeError:
                pass    

sums = np.memmap(open('tmp.paprica.mmp', 'w+b'), shape = genome_data.index.shape[0], dtype = 'uint64')

Parallel(n_jobs = -1)(delayed(count_ec)(sums, i)
for i in range(0, len(genome_data.index)))
    
eci = int(sums.sum() * 2) # Count_ec is undercounting and not clear why.  Multiply by 2 to insure large enough array.

## Delete mmp

os.remove('tmp.paprica.mmp')
                            
## Create numpy array for data and a 1D array that will become dataframe index.
## You can probably parallelize this as above, but going to take some effort.
                            
prot_array = np.empty((eci,9), dtype = 'object')
prot_array_index = np.empty(eci, dtype = 'object')

## Iterate through all the files in refseq and find the gbk files again.  Store
## the information necessary to create a Genbank record of each feature in the
## array.

i = 0

for d in genome_data.index:
    domain = genome_data.loc[d, 'domain']    
    strain = genome_data.loc[d, 'tax_name']
    
    ## For the domain eukarya, the nuc records are not available as part of the
    ## Genbank format file, they need to be aquired separately and indexed so
    ## that they can be matched with the prot records.
        
    if domain == 'eukarya':
        eukarya_nt_dict = {}
        
        for record in SeqIO.parse(ref_dir + domain + '/refseq/' + d + '/' + d + '.nt.fa', 'fasta'):
            seq_name = str(record.description).split('NCGR_SEQ_ID=')[1]
            seq_name = seq_name.split(' /')[0]
            
            ## Dictionary maps peptide name to nucleotide sequence.
            
            eukarya_nt_dict[seq_name] = str(record.seq)
                
    for f in os.listdir(ref_dir + domain + '/refseq/' + d):
        if f.endswith('gbff'):
            
            try:
                for record in SeqIO.parse(ref_dir + domain + '/refseq/' + d + '/' + f, 'genbank'):
                    for feature in record.features:
                        if feature.type == 'CDS':
                            if 'EC_number' in list(feature.qualifiers.keys()):
                                
                                ## These qualifiers must be present.
                            
                                try:
                                    protein_id = feature.qualifiers['protein_id'][0]
                                    trans = feature.qualifiers['translation'][0]
                                    ec = feature.qualifiers['EC_number']
                                    prod = feature.qualifiers['product'][0]
                                except KeyError:
                                    continue
                                
                                ## Get the nucleotide sequence.
                                
                                if domain != 'eukarya':
                                    
                                    ## Start and end are captured here, but these aren't
                                    ## always correct, which is why I'm now using the feature.extract method.                                    
                                    
                                    start = int(feature.location.start)
                                    end = int(feature.location.end)
                                    seq = str(feature.extract(record).seq)
                                else:
                                    start = 0
                                    end = 0
                                    
                                    try:
                                        seq = eukarya_nt_dict[protein_id.rstrip('_1')]
                                    except KeyError:
                                        seq = 'no_nucleotide_sequence_found'
                                    
                                ## Because enzymes can be identified by combinations of EC numbers,
                                ## need to keep multiple together, and ordered in a consistent way.
                                    
                                if len(ec) > 1:
                                    ec.sort()
                                    ec = ['|'.join(ec)]
                                
                                prot_array_index[i] = protein_id
                                prot_array[i,0] = d
                                prot_array[i,1] = domain
                                prot_array[i,2] = strain
                                prot_array[i,3] = ec[0]
                                prot_array[i,4] = seq
                                prot_array[i,5] = trans
                                prot_array[i,6] = prod
                                prot_array[i,7] = start
                                prot_array[i,8] = end
                                
                                i = i + 1
                                print(d, i, 'out of around', int(eci/2), protein_id, ec[0])
                                
            ## For some assemblies an error is raised on a second(?) record identified
            ## in the Genbank file.  It isn't clear why this is happening, pass the error
            ## here.
                                
            except AttributeError:
                pass

## Convert array to pandas dataframe

columns = ['genome', 'domain', 'tax_name', 'EC_number', 'sequence', 'translation', 'product', 'start', 'end']                                    
prot_df = pd.DataFrame(prot_array, index = prot_array_index, columns = columns)

## Determine how often each translation appears.  CDS with a translation
## that is not unique should not be used for taxonomic profiling with
## metagenomes.  Currently not taxonomic profiling anyway.

prot_counts = pd.DataFrame(prot_df['translation'].value_counts())
prot_counts.columns = ['trans_n_occurrences'] # The number of times that the sequence appears across all genomes.

## Add this information to prot_df.

prot_df = pd.merge(prot_df, prot_counts, left_on = 'translation', right_index = True)

## Determine how often each sequence appears.

nuc_counts = pd.DataFrame(prot_df['sequence'].value_counts())
nuc_counts.columns = ['cds_n_occurrences'] # The number of times that the sequence appears across all genomes.

## Add this information to prot_df.

prot_df = pd.merge(prot_df, nuc_counts, left_on = 'sequence', right_index = True)

## Now that you know which are duplicates, make nonredundant and print out to
## csv.  This is the basis of the paprica-mg database for metagenomic analysis.

shutil.rmtree(ref_dir + 'paprica-mgt.database', ignore_errors = True)
os.mkdir(ref_dir + 'paprica-mgt.database')

prot_nr_trans_df = prot_df.drop_duplicates(subset = ['translation'])
prot_nr_trans_df.to_csv(ref_dir + 'paprica-mgt.database/paprica-mg.ec.csv.gz', compression = 'gzip')

## For metatranscriptome analysis we want nonredundant sequences,
## not translations.  Only those that appear only once should be
## used for taxonomic bining, or genome-level analyses however.

prot_unique_cds_df = prot_df.drop_duplicates(subset = ['sequence'])
prot_unique_cds_df = prot_unique_cds_df[prot_unique_cds_df.sequence != 'no_nucleotide_sequence_found']
prot_unique_cds_df.to_csv(ref_dir + 'paprica-mgt.database/paprica-mt.ec.csv.gz', compression = 'gzip')

## Make a nonredundant fasta for the metagenomic analysis database.

with gzip.open(ref_dir + 'paprica-mgt.database/paprica-mg.fasta.gz', 'wt') as fasta_out:
    for row in prot_nr_trans_df.iterrows():
        protein_id = row[0]
        translation = row[1]['translation']
        print('making fasta file', protein_id)
        print('>' + protein_id, file=fasta_out)
        print(translation, file=fasta_out)

subprocess.call('diamond makedb --in ' + ref_dir + 'paprica-mgt.database/paprica-mg.fasta.gz -d ' + ref_dir + 'paprica-mgt.database/paprica-mg', shell = True, executable = executable) 

## Make an unique fasta for the metatranscriptomic analysis database.

with gzip.open(ref_dir + 'paprica-mgt.database/paprica-mt.fasta.gz', 'wt') as fasta_out:
    for row in prot_unique_cds_df.iterrows():
        protein_id = row[0]
        sequence = row[1]['sequence']
        print('making fasta file', protein_id)
        print('>' + protein_id, file=fasta_out)
        print(sequence, file=fasta_out)

subprocess.call('bwa index ' + ref_dir + 'paprica-mgt.database/paprica-mt.fasta.gz', shell = True, executable = executable)
                        
                        
        