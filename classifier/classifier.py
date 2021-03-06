import os.path
import time
import warnings
import math

from glob import glob
import pandas as pd
import pickle
import mahotas as mh
from mahotas.features import lbp
from mahotas.features import surf
import numpy as np
from sklearn import cross_validation
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.grid_search import GridSearchCV

warnings.filterwarnings("ignore", category=DeprecationWarning) 

classes = ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9']
    

def compute_texture(fname):
    '''
    Compute features for an image
    ------------------------------
    Parameters
    ----------
    fname : str
        filepath for image to process
    Returns
    -------
    ndarray
        1-D array of features
    '''
    im = mh.colors.rgb2grey(mh.imread(fname))
    im = im.astype(np.uint8)
    return mh.features.haralick(im).ravel()


def compute_lbp(fname):
    '''
    Compute features for an image
    ------------------------------
    Parameters
    ----------
    fname : str
        filepath for image to process
    Returns
    -------
    ndarray
        linear binary patterns
    '''
    imc = mh.imread(fname)
    im = mh.colors.rgb2grey(imc)
    return lbp(im, radius=8, points=6)


def accuracy(featureType, features, labels, predict=False, test_features=[], test_images=[]):
    ''' 
    Trains classifier, makes predictions and computes best score and parameters for classifier
    ------------------------------
    Parameters
    ----------
    featureType : str
        feature set

    features : ndarray
        1-D array of train features

    labels : ndarray
        1-D array of labels

    predict : Boolean
        True to make predictions

    test_features : ndarray
        1-D array of test features

    test_images : ndarray
        1-D array of image filepaths

    Returns
    -------
    score : float
        accuracy score

    best_parameters : dict
        parameters dictionary with the best results

    '''

    param_grid_LR = {'C': [0.001, 0.01, 0.1, 1, 10, 100, 1000] }
    cv = cross_validation.KFold(n=len(features), n_folds=10, shuffle=False,
                               random_state=None)
    log_r = LogisticRegression(solver="lbfgs", multi_class="multinomial")
    CV_log = GridSearchCV(estimator=log_r, param_grid=param_grid_LR, cv=cv)

    classifier = Pipeline([
                  ('preproc', StandardScaler()),
                  ('log',CV_log)
                  ])

    # Model One vs Rest with Random Forests
    # param_grid_RF = { 
    #     'n_estimators': [100, 700],
    #     'max_features': ['auto', 'sqrt', 'log2']
    # }
    # classifier = [RandomForestClassifier(n_jobs=-1,n_estimators=100) for i in classes]
    # CV_rfcs = [GridSearchCV(estimator=clf, param_grid=param_grid_RF, cv=cv) for clf in classifier]

    if type(classifier) is list:
        print("Testing Random Forest classifer")
        scores = []
        for i, clf in zip(classes, CV_rfcs):
            clf.fit(features, labels)
            score = clf.best_score_
            best_parameters = clf.best_params_
            scores.append(score)
            print('Trained {} score {}'.format(i, score))
        score = np.mean(scores)
        print('Done training')
        
        if predict:
            print("Predicting test images")
            results = []
            for index, clf in enumerate(CV_rfcs):
                predictions = clf.predict_proba(test_features)[:, index]
                results.append(predictions)
            create_submission(featureType, results, test_images)
        return score, best_parameters
    else:
        print("Testing Logistic Regression classifer")
        classifier.fit(features, labels)
        score = CV_log.best_score_
        best_parameters = CV_log.best_params_
        if predict:
            preds = classifier.predict_proba(test_features)
            create_submission(featureType, preds, test_images)
        return score, best_parameters


def print_results(scores):
    ''' 
    Saves score and best parameters in txt file
    ------------------------------
    Parameters
    ----------
    scores : tuple
        tuple of feature type name, score, best parameters
    '''

    with open('submissions/results_LR.image.txt', 'a') as output:
        for k, v, p in scores:
            output.write('Accuracy with Logistic Regression [{0}]: {1:.1%}\n Best parameters: {2}\n'.format(
                k, v, p))


def create_submission(featureType, preds, images):
    ''' 
    Creates submission csv for the particular feature type
    ------------------------------
    Parameters
    ----------
    featureType : str
        type of features being used

    preds : ndarray
        predicted probabilities for each class

    images : ndarray
        1-D array of image filepaths

    '''

    print('Creating submission')
    if(type(preds) is not list):
        preds = preds.transpose()
    c0, c1, c2, c3, c4, c5, c6, c7, c8, c9 = preds
    submission_data = pd.DataFrame({    
        'img':  [x.split('/')[-1] for x in images],
        'c0': c0,
        'c1': c1,
        'c2': c2,
        'c3': c3,
        'c4': c4,
        'c5': c5,
        'c6': c6,
        'c7': c7,
        'c8': c8,
        'c9': c9,
    })
    
    fileName = '{}/{}_submission.csv'.format('submissions', featureType)
    
    submission_data[['img', 'c0', 'c1', 'c2', 'c3',
         'c4', 'c5', 'c6', 'c7', 'c8', 'c9']].to_csv(fileName, index=False)


def get_images(train):
    ''' 
    Get train or test images
    ------------------------------
    Parameters
    ----------
    train : Boolean
        True for train images

    Returns
    ----------
    images : iterator
        iterator of image filepaths

    '''

    classes = ['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9']
    images = []
    # Use glob to get all the train_images
    if train:
        for i in classes:
            images += glob('{}/{}/{}/*.jpg'.format('imgs', 'train', i))

    # Use glob to get all the test_images
    else:
        images += glob('{}/{}/*.jpg'.format('imgs', 'test'))

    images.sort()
    return images


def get_kmeans(k, train, descriptors):
    '''
    Create k means with surf descriptors
    ------------------------------
    Parameters
    ----------
    k : int
        number of clusters

    train : Boolean
        True for creating k means for train surf descriptors

    images : ndarray
        1-D array of image filepaths

    Returns
    ----------
    km : object
        MiniBatchKmeans
    '''

    iterations = 30
    km = get_obj(train, 'k_means')

    if km != None:
        return km
    else:    
        start = time.clock()
        km = MiniBatchKMeans(n_clusters=k, batch_size=1000, n_init=iterations)
        print('Clustering with K-means...')
        km.fit(descriptors)
        end = time.clock()
        print "Time for running %d iterations of K means for %d samples = %f seconds" % (iterations, len(descriptors), end - start)
        # save k_means for later
        print("Saving K-means")
        save_obj(train, 'k_means', km)
        return km


def get_obj(train, objectContent):
    ''' 
    Unpickling object
    ------------------------------
    Parameters
    ----------
    train : Boolean
        if True, get object from train folder

    objectContent : str
        type of content inside obj file

    Returns
    ----------
    pickled object or None
    '''

    if train:
        filename = 'objects/train/train_{}.obj'.format(objectContent)
    else: 
        filename = 'objects/test/test_{}.obj'.format(objectContent)

    if os.path.exists(filename):
        print("Getting object %s" % filename)
        with open(filename, 'rb') as fp:
            return pickle.load(fp)
    else: 
        return None
        

def save_obj(train, objectContent, obj):
    ''' 
    Pickle objects
    ------------------------------
    Parameters
    ----------
    train : Boolean
        if True, get object from train folder

    objectContent : str
        type of content inside obj file

    obj : object
        object to save

    '''

    if train:
        filename = 'objects/train/train_{}.obj'.format(objectContent)
    else: 
        filename = 'objects/test/test_{}.obj'.format(objectContent)

    with open(filename, 'wb') as fp:
        pickle.dump(obj, fp)
        print("Saved %s" % filename)


def get_features(train, images):
    ''' 
    Extract features for train or test images
    ------------------------------
    Parameters
    ----------
    train : Boolean
        if Train, get features for train

    images : ndarray
        1-D array of image filepaths

    Returns 
    ----------
    haralicks : ndarray
        1-D flattened array of haralicks features

    lbps : ndarray
        1-D flattened array of linear binary patterns
    
    labels : ndarray
        1-D array of labels for train images

    surf_descriptors : ndarray
        1-D flattened array of surf descriptors feature
    '''

    haralicks = []
    lbps = []
    labels = []
    alldescriptors = []

    if train:
        k = math.sqrt(22425/2)
        path = 'objects/train/'
    else:
        k = math.sqrt(79727/2)
        path = 'objects/test/'

    object_dir_file_num = len([name for name in os.listdir(path) if name.endswith('.obj')])

    if object_dir_file_num == 5:
        haralicks = get_obj(train, 'haralicks')
        lbps = get_obj(train, 'lbps')
        labels = get_obj(train, 'labels')
        surf_descriptors = get_obj(train, 'surfdescriptors')
    else:
        for i, fname in enumerate(images):
            texture = compute_texture(fname)
            binary_patt = compute_lbp(fname)
            haralicks.append(texture)
            lbps.append(binary_patt)
            if train:
                label = fname.split('/')[2]
                labels.append(label)
            
            im = mh.imresize(mh.imread(fname, as_grey=True), (600, 450))
            im = im.astype(np.uint8)

            # Dense sampling of surf 
            surf_desc = surf.dense(im, spacing=16)
            # regular surf 
            # surf.surf(im, descriptor_only=True)
            print('Image {}: {}'.format(i, surf_desc.shape))
            alldescriptors.append(surf_desc)
    
        concatenated = np.concatenate(alldescriptors)
        print('Number of descriptors: {}'.format(
                len(concatenated)))
        concatenated = concatenated[::64]
        
        km = get_kmeans(k, train, concatenated)
        surf_descriptors = []
        for d in alldescriptors:
            c = km.predict(d)
            surf_descriptors.append(np.bincount(c, minlength=k))

        surf_descriptors = np.array(surf_descriptors, dtype=float)
        haralicks = np.array(haralicks)
        lbps = np.array(lbps)
        labels = np.array(labels)

        save_obj(train, 'surfdescriptors', surf_descriptors)
        save_obj(train, 'haralicks', haralicks)
        save_obj(train, 'lbps', lbps)
        save_obj(train, 'labels', labels)


    return haralicks, lbps, labels, surf_descriptors



# get images for train and test
train_images = get_images(True)
test_images = get_images(False)

# get features for train images
haralicks, lbps, labels, surf_descriptors = get_features(True, train_images)
combined = np.hstack([lbps, haralicks])
combined_all = np.hstack([haralicks, lbps, surf_descriptors])

# get features for test images
test_haralicks, test_lbps, test_labels, test_surf = get_features(False, test_images)
test_combined = np.hstack([test_lbps, test_haralicks])
test_combined_all = np.hstack([test_haralicks, test_lbps, test_surf])

# create classifiers and get the best score and parameters for each possible feature set
scores_base, params1 = accuracy('base', haralicks, labels, True, test_haralicks, test_images)
scores_lbps, params2 = accuracy('lbps', lbps, labels, True, test_lbps, test_images)
scores_surf, params3 = accuracy('surf', surf_descriptors, labels, True, test_surf, test_images)
scores_combined, params4 = accuracy('combined', combined, labels, True, test_combined, test_images)
scores_combined_all, params5 = accuracy('combined_all', combined_all, labels, True, test_combined_all, test_images)

# save results in "results_LR.image.txt"
print_results([
        ('base', scores_base, params1),
        ('lbps', scores_lbps, params2),
        ('surf', scores_surf, params3),
        ('combined', scores_combined, params4),
        ('combined_all', scores_combined_all,params5),
        ])