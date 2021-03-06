# -*- coding: utf-8 -*-

import collections
import os, sys
import re
import cPickle as pkl

import numpy as np

from batch_loader import BatchLoader
from .functional import *

import torch as t

"""
This code expects word_embeddings, word vocab, and char vocab already generated using 
train_embedding.py
"""

class DataHandler:

    def __init__(self, vocab_files, \
                 generator_file, \
                 batch_size=32, load_generator=True):

        self.batch_size = batch_size
        self.generator_data = None

        if generator_file:
            with open(generator_file, 'rb') as f:
                self.generator_data = [pkl.load(f)]
                    
        self.gen_batch_loader = BatchLoader(self.generator_data, vocab_files, sentence_array=True)
        self.vocab_size = self.gen_batch_loader.words_vocab_size
        
    def load_discriminator(self, discriminator_file):

        print 'Loading Discriminator Data'
        with open(discriminator_file, 'rb') as f:
            self.sentiment_discriminator_X, self.sentiment_discriminator_Y = pkl.load(f)

        # Train Data : Dev Data => 1:3
        self.sentiment_total_size = self.batch_size * 3 *  (len(self.sentiment_discriminator_X) // (3 * self.batch_size) )
        self.total_sentiment = len(set(self.sentiment_discriminator_Y))

        # Divide into 1:3
        self.train_sentiment_size = 2 * self.sentiment_total_size // 3
        self.dev_sentiment_size = self.sentiment_total_size // 3

        self.num_train_sentiment_batches = self.train_sentiment_size / self.batch_size
        self.num_dev_sentiment_batches = self.dev_sentiment_size / self.batch_size

        print 'Total Sentiment size: %d' % self.sentiment_total_size
        print 'Train sentiment size: %d' % self.train_sentiment_size
        print 'Dev sentiment size: %d' % self.dev_sentiment_size

        indices = np.arange(self.sentiment_total_size)
        np.random.shuffle(indices)

        self.sentiment_train_indices = indices[:self.train_sentiment_size]
        self.sentiment_dev_indices = indices[self.train_sentiment_size:(self.dev_sentiment_size+self.train_sentiment_size)]

        data_words = [line.split() for line in self.sentiment_discriminator_X]

        # This has both train and dev data
        self.sentiment_discriminator_X = [list(map(self.gen_batch_loader.word_to_idx.get, line)) for line in data_words]
        self.sentiment_discriminator_Y = map(int, self.sentiment_discriminator_Y)

    def get_sentiment_train_batch(self, batch_index):

        batch_indices = np.arange(batch_index*self.batch_size, (batch_index+1)*self.batch_size)

        batch_train_X = [self.sentiment_discriminator_X[self.sentiment_train_indices[x]] for x in batch_indices]
        batch_train_Y = [self.sentiment_discriminator_Y[self.sentiment_train_indices[x]] for x in batch_indices]
        
        return batch_train_X, batch_train_Y

    def get_sentiment_dev_batch(self, batch_index):

        batch_indices = np.arange(batch_index*self.batch_size, (batch_index+1)*self.batch_size)

        batch_dev_X = [self.sentiment_discriminator_X[self.sentiment_dev_indices[x]] for x in batch_indices]
        batch_dev_Y = [self.sentiment_discriminator_Y[self.sentiment_dev_indices[x]] for x in batch_indices]

        return batch_dev_X, batch_dev_Y

    def create_sentiment_batch(self, x_dg):

        # get batch sentence len   
        batch_sentence_len = [len(sentence) for sentence in x_dg]
        max_seq_len = np.amax(batch_sentence_len)

        for i, line in enumerate(x_dg):
            line_len = batch_sentence_len[i]
            to_add = max_seq_len - line_len
            x_dg[i] = line + [self.gen_batch_loader.word_to_idx[self.gen_batch_loader.pad_token]] * to_add
        
        x_dg = np.array(x_dg)
        x_dg = x_dg.reshape((len(x_dg), max_seq_len))
        x_dg = t.from_numpy(x_dg)

        return x_dg
        
    def create_generator_batch(self, x_gen, use_cuda):

        gen_batch_sen_len = [len(sentence) for sentence in x_gen]

        """
        one_hot = t.FloatTensor(self.vocab_size)
        one_hot = one_hot.zero_()
        one_hot[self.gen_batch_loader.word_to_idx[self.gen_batch_loader.pad_token]] = 1

        if use_cuda:
            one_hot = one_hot.cuda()
        """
        
        max_seq_len = np.amax(gen_batch_sen_len)

        for i, line in enumerate(x_gen):
    
            line_len = len(line)
            to_add = max_seq_len - line_len
            # line = line + [one_hot]*to_add
            line  = line + [self.gen_batch_loader.word_to_idx[self.gen_batch_loader.pad_token]] * to_add
            # line = t.stack(line, dim=0)
            x_gen[i] = line
    
        x_gen = t.from_numpy(np.asarray(x_gen))
        
        return x_gen

                
    def feature_from_indices(self, x):
        """
        Get one-hot vector for x
        """
        
        # x : (batch_size,  max_seq_len_in_batch)
        x_inp = t.unsqueeze(x, 2)
        
        batch_size = x.size(0)
        max_seq_len_in_batch = x.size(1)
        
        one_hot = t.FloatTensor(batch_size, max_seq_len_in_batch, self.vocab_size)
        one_hot = one_hot.zero_()
        one_hot.scatter_(2, x_inp, 1)

        return one_hot
