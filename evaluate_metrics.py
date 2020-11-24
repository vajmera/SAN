'''
Calculates the precision recall score given a model checkpoint
Must run like below (can change the checkpoint and batch size)
!python precision_recall.py --classifier_on --v2_on --load_checkpoint 27 --batch_size 128
'''

import os
import logging
import json
import torch
from sklearn.metrics import confusion_matrix, average_precision_score, f1_score
import numpy as np
from src.model import DocReaderModel
from src.batcher import load_meta, BatchGen
from config import set_args
from my_utils.utils import set_environment
from my_utils.log_wrapper import create_logger
from my_utils.squad_eval import evaluate
from my_utils.data_utils import predict_squad, gen_name, gen_gold_name, load_squad_v2_label, compute_acc
from my_utils.squad_eval_v2 import my_evaluation as evaluate_v2

args = set_args()
# set model dir
model_dir = args.model_dir
os.makedirs(model_dir, exist_ok=True)
model_dir = os.path.abspath(model_dir)

# set environment
set_environment(args.seed, args.cuda)
# setup logger
logger =  create_logger(__name__, to_disk=True, log_file=args.log_file)

def load_squad(data_path):
    with open(data_path) as dataset_file:
        dataset_json = json.load(dataset_file)
        dataset = dataset_json['data']
        return dataset

def main():
    logger.info('Launching the SAN')
    opt = vars(args)
    logger.info('Loading data')

    version = 'v2' if args.v2_on else 'v1'
    gold_version = 'v2.0' if args.v2_on else 'v1.1'


    dev_path = gen_name(args.data_dir, args.dev_data, version)
    dev_gold_path = gen_gold_name(args.data_dir, args.dev_gold, gold_version)
    dev_labels = load_squad_v2_label(dev_gold_path)

    embedding, opt = load_meta(opt, gen_name(args.data_dir, args.meta, version, suffix='pick'))
    dev_data = BatchGen(dev_path,
                          batch_size=args.batch_size,
                          gpu=args.cuda, is_train=False, elmo_on=args.elmo_on)

    dev_gold = load_squad(dev_gold_path)

    state_dict = None
    if(args.load_checkpoint !=0):
        start_epoch = args.load_checkpoint + 1
        checkpoint_file = 'checkpoint_{}_epoch_{}.pt'.format(version, args.load_checkpoint)
        checkpoint_path = os.path.join(args.model_dir,checkpoint_file)
        logger.info('path to prev checkpoint is {}'.format(checkpoint_path))
        checkpoint = torch.load(checkpoint_path, map_location=torch.device('cpu'))
        state_dict = checkpoint['state_dict']

    # Set up the model
    logger.info('Loading model ...')
    model = DocReaderModel(opt, embedding,state_dict)
    model.setup_eval_embed(embedding)
    logger.info('done')

    if args.cuda:
        model.cuda()

    # dev eval
    logger.info('Predicting ...')
    results, labels = predict_squad(model, dev_data, v2_on=args.classifier_on)
    logger.info('done')

    # get actual and predicted labels (as lists)
    actual_labels = []
    predicted_labels = []
    dropped = 0
    for key in dev_labels.keys(): # convert from dictionaries to lists
        try:
            actual_labels.append(dev_labels[key])
            predicted_labels.append(labels[key])
        except:
            dropped += 1
    print(f'dropped: {dropped}')

    actual_labels = np.array(actual_labels)
    predicted_labels = np.array(predicted_labels)

    # convert from continuous to discrete
    actual_labels = (actual_labels > args.classifier_threshold)
    predicted_labels = (predicted_labels > args.classifier_threshold)

    # Print all metrics
    print('accuracy', 100 * sum(abs(predicted_labels-actual_labels)) / len(actual_labels), '%')
    print('confusion matrix', confusion_matrix(predicted_labels, actual_labels))
    print('average precision recall score', average_precision_score(predicted_labels, actual_labels))
    print('f1 score', f1_score(predicted_labels, actual_labels))

if __name__ == '__main__':
    main()
