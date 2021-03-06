import cv2
import numpy as np
import os
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import math
import re
import time
import ssl
import urllib.request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

class ImageSimilarityAnalyser:
    score_same_image = 0

    def __init__(self, project_name, data_source, algorithm_params, subset_df, pickle=False, image_from='volume', data_dir=None):
        self.project_name = project_name
        self.data_source = data_source
        self.algorithm_params = algorithm_params
        self.image_from = image_from
        self.data_dir = data_dir
        self.subset_df = subset_df
        self.project_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.project_name)
        if self.data_source == 2:
            self.images_path = os.path.join("C:/Users/mhartman/PycharmProjects/FlickrFrame", self.project_name, f'images_{self.project_name}')
        else:
            self.images_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.project_name, f'images_{self.project_name}')
        self.algorithm = self.algorithm_params['algorithm']
        self.lowe_ratio = self.algorithm_params['lowe_ratio']

        print("--" * 30)
        print("Initialising Computer Vision with ImageSimilarityAnalysis Class")
        self.image_objects, self.feature_dict, self.nr_images = self.file_loader()
        print("--" * 30)
        print("Load images - done.")
        if self.algorithm == 'SIFT':
            self.alg_obj = cv2.xfeatures2d.SIFT_create(contrastThreshold=0.04, edgeThreshold=10)

        elif self.algorithm == 'SURF':
            self.alg_obj = cv2.xfeatures2d.SURF_create()

        elif self.algorithm == 'ORB':
            self.alg_obj = cv2.ORB_create(nfeatures=1500)

        print(f"Using algorithm {self.algorithm}")
        self.compute_keypoints()
        print("--" * 30)
        print("Compute image keypoints - done.")
        self.df, self.df_similarity = self.match_keypoints(lowe_ratio=self.lowe_ratio, pickle_similarity_matrix=pickle)
        print("--" * 30)
        print("Compute image similarity dataframe - done.")

        # print(f"Duration: {end - start} seconds")

        # with open(path_performance_log, 'a') as log:
        #     log.write(f"{self.algorithm}, processed files: {self.nr_images}, duration: {end-start}\n")

        # self.visualise_matches('img9', 'img10', top_matches=20)
        # self.visualise_matches('img8', 'img9', top_matches=20)
        # self.visualise_matches('img8', 'img10', top_matches=20)
        print("Adding new features to dataframe")
        self.add_features()
        del self.alg_obj
        del self.image_objects
        # self.plot_results(top_comparisons=20, top_matches=20)
        print("--" * 30)
        print("--" * 30)
        print("ImageSimilarityAnalysis Class - done")

    def file_loader(self):
        '''
        image_from specifies where the image data shall be taken from
        options: 'path': from the image_storage /mnt1 volume
                'url': from direct requests to the remote farm server where the images are hosted

        :param image_from:
        :return:
        '''
        def url_to_image(target_url, session):
            # download the image, convert it to a NumPy array, and then read it into OpenCV format
            # content = urllib.request.urlopen(url, context=ssl._create_unverified_context())
            content = session.get(target_url, verify=False, stream=True)
            content.raise_for_status()
            content = content.content
            image = np.asarray(bytearray(content), dtype="uint8")
            image = cv2.imdecode(image, cv2.IMREAD_GRAYSCALE)
            # return the image
            return image

        def volume_to_image(id_hash):
            first_3b = id_hash[:3]
            sec_3b = id_hash[3:6]
            image_path = f"C:/Users/mhartman/PycharmProjects/IMAGE_SCRAPE_TEST/{first_3b}/{sec_3b}/{id_hash}.jpg"
            with open(image_path, 'rb') as f:
                content = f.read()
            image = np.asarray(bytearray(content), dtype="uint8")
            image = cv2.imdecode(image, cv2.IMREAD_GRAYSCALE)
            return image

        def path_to_image(image_dir, img):
            return os.path.join(image_dir, img)

        # turn off SSL warnings
        requests.packages.urllib3.disable_warnings()
        #load image as grayscale since following 3 algoithms ignore RGB information
        image_objects = {}
        feature_dict = {}

        if self.data_source == 1: #PostgreSQL db
            ids = self.subset_df.index.values
            img_urls = self.subset_df.loc[:, 'download_url']
            id_hashes = self.subset_df.loc[:, 'id_hash']
            nr_images = img_urls.shape[0]
            not_found = 0

            if self.image_from == 'url':
                # Create session
                with requests.Session() as session:
                    # session.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0"}
                    # change retry settings to overcome HTTPSConnectionPool error - target server refuses connections due to many per time
                    retry = Retry(total=3, read=3, connect=3, backoff_factor=1)
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    for counter, (img_id, url) in enumerate(zip(ids, img_urls), 1):
                        try:
                            '''
                            HERE FIX URL <MISSING SCHEMA> ERROR
                            append 'http:' if not already present
                            '''
                            if url[:2] == '//':
                                url = 'http:' + url
                            # image_objects[img_id] = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
                            image_objects[img_id] = url_to_image(url, session)
                            feature_dict[img_id] = {}
                            print(f'\r{counter} of {nr_images} images', end='')
                        except Exception as e:
                            print(f"{e}")
                            if isinstance(e, requests.exceptions.ConnectionError):
                                print("CONNECTIONERROR - TRYING OTHER DNS REQUEST")
                                hostname = "google.com"  # example
                                response = os.system("ping -c 1 -w2 " + hostname + " > /dev/null 2>&1")
                                # and then check the response...
                                if response == 0:
                                    print(hostname, ' is up!')
                                else:
                                    print(hostname, ' is down!')
                            not_found += 1
                    print(f"\nNot found images: {not_found}")
                    if not_found == len(ids):
                        amount = 5
                        print(f"Sleep {amount}s due to all images raised errors")
                        time.sleep(amount)

            elif self.image_from == 'volume':
                for counter, (img_id, id_hash) in enumerate(zip(ids, id_hashes), 1):
                    try:
                        image = volume_to_image(id_hash)
                        image_objects[img_id] = image
                        feature_dict[img_id] = {}
                        print(f'\r{counter} of {nr_images} images', end='')
                    except Exception as e:
                        print(f"Image: {id_hash}; Error: {e}")
                        not_found += 1
                print(f"\nNot found images: {not_found}")

        elif self.data_source == 2: #Flickr API
            images = [os.path.join(self.images_path, file) for file in os.listdir(self.images_path) if os.path.isfile(os.path.join(self.images_path, file))]
            nr_images = len(images)
            '''
            load images
            ONLY of the specific subset!
            '''
            needed_ids = self.subset_df.index.values
            print(f"Number of images to process: {len(needed_ids)}")
            for index, img in enumerate(images):
                pattern = r"([\d]*)\.jpg$"
                img_id = int(re.search(pattern, img).group(1))
                if img_id in needed_ids:
                    image_objects[img_id] = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
                    feature_dict[img_id] = {}
        #using existing data directory
        elif self.data_source == 3:
            needed_ids = self.subset_df.index.values
            image_dir = os.path.join(self.data_dir, f'images_{self.data_dir.split("/")[-1]}')
            nr_images = 0
            for img in os.listdir(image_dir):
                nr_images += 1
                img_id = int(img[:-4])
                if img_id in needed_ids:
                    img_path = path_to_image(image_dir, img)
                    image_objects[img_id] = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    feature_dict[img_id] = {}
            print(f"Number of images to process: {len(needed_ids)}")

        return image_objects, feature_dict, nr_images

    def compute_keypoints(self):
        '''
        compute the keypoints and the corresponding descriptors
        which allow the keypoints to be functional even with 
        image rotation and distortion

        Algorithms: SIFT, SURF, ORB
        '''

        for obj in self.image_objects:
            #the None defines if a mask shall be used or not
            try:
                img_obj = self.image_objects[obj]
                keypoints, descriptors = self.alg_obj.detectAndCompute(img_obj, None)
            except Exception as e:
                print(f"Img_obj: {img_obj}, Img_id: {obj} \n{e}; Compute_keypoint error")
                keypoints = []
                descriptors = []
            self.feature_dict[obj]['kp'] = keypoints
            self.feature_dict[obj]['ds'] = descriptors

    def match_keypoints(self, lowe_ratio=0.7, pickle_similarity_matrix=True):
        '''
        Brute Force
        Matching between the different images
        - Create pandas dataframe to store the matching output
        of every image (n) with the set in a 2D matrix of n^2 entries
        '''
        self.lowe_ratio = lowe_ratio
        #one to store the matches, the other for the later computed similarity scores
        df = pd.DataFrame(columns=self.image_objects.keys(), index=self.image_objects.keys())
        df_similiarity = pd.DataFrame(columns=self.image_objects.keys(), index=self.image_objects.keys())
        #normalising function dependant on used algorithm - NORM_HAMMING good for orb
        bf = cv2.BFMatcher() #cv2.NORM_L1, crossCheck=True
        #store already sorted match results in corresponding matrix cells
        indexes = df.index.values
        columns = df.columns.values
        '''
        here reduce the redundancy
        by avoiding to check the same comparisons twice
        (since similarity between img1 and img2 is the same as the similarity between img2 and img1)                
        '''
        for check1, index in enumerate(indexes):
            for check2, column in enumerate(columns):
                if check2 >= check1 and check2 != check1:
                    try:
                        value = bf.knnMatch(self.feature_dict[index]['ds'], self.feature_dict[column]['ds'], k=2)
                        df.set_value(index, column, value)
                    except Exception as e:
                        print(f"{e} match_keypoints error: NaN value set")
                        df.set_value(index, column, np.nan)

        print("Populated dataframe with image matches - done.")
        recorded_match_lengths = []
        #iterate over dataframe to calculate similarity score and populate second df
        for row in indexes: #better use .iteritems()
            for col in columns:
                # distances = []
                similar_regions = []
                matches = df.loc[row, col]
                if isinstance(matches, (list,)): #would work too: type(matches) == list
                    if len(matches) == 0:
                        df_similiarity.set_value(row, col, 0)
                    else:
                        try:
                            for m, n in matches:
                                if m.distance < self.lowe_ratio * n.distance:
                                    similar_regions.append([m])
                            score = len(similar_regions)
                        except Exception as e:
                            print("//" * 30)
                            print(f"Error {e} encountered...")
                            print("//" * 30)
                            score = 0

                        df_similiarity.set_value(row, col, score)
                    recorded_match_lengths.append(len(matches))

                elif math.isnan(matches):
                    #has to be zero not nan for the clustering to work
                    df_similiarity.set_value(row, col, 0)

        recorded_match_lengths = sorted(recorded_match_lengths, key=lambda x: x)
        '''
        fill in missing fields that were previously skipped due to computational reasons caused by same image comparison 
        -> Mirror dataframe along the diagonal
        All values are needed to form the individual image similarity features for each media object!
        '''
        [df_similiarity.set_value(index, column, df_similiarity.loc[column, index])
         for check1, index in enumerate(indexes)
            for check2, column in enumerate(columns) if check2 < check1 and check1 != 0]
        '''
        Fill in similarity score of 0
        for all comparisons between the same images -> the diagonal
        '''
        [df_similiarity.set_value(index, column, ImageSimilarityAnalyser.score_same_image)
         for check1, index in enumerate(indexes)
            for check2, column in enumerate(columns) if check2 == check1]

        if pickle_similarity_matrix:
            print("Pickling similarity dataframe...")
            if re.search(r"motive", self.workpath):
                df_similiarity.to_pickle("{}similarity_matrix_motive_{}_{:%Y_%m_%d}_{}.pkl".format(self.project_path, self.threshold, datetime.datetime.now(), self.algorithm))

            elif re.search(r"noise", self.workpath):
                df_similiarity.to_pickle("{}similarity_matrix_noise_{}_{:%Y_%m_%d}_{}.pkl".format(self.project_path, self.threshold, datetime.datetime.now(), self.algorithm))

        return df, df_similiarity

    def visualise_matches(self, img1, img2, top_matches=20):
        img_1_object = self.image_objects[img1]
        img_2_object = self.image_objects[img2]
        kp_1 = self.feature_dict[img1]['kp']
        kp_2 = self.feature_dict[img2]['kp']
        matches = self.df.loc[img1, img2][:top_matches]

        result = cv2.drawMatches(img_1_object, kp_1, img_2_object, kp_2, matches, None, flags=2)
        cv2.imshow("Image", result)
        cv2.waitKey(0)
        cv2.destroyWindow("Image")

    def plot_results(self, top_comparisons=20, top_matches=20, score_plot=False, plot=True, barchart=False):

        font = {'size': 5}
        plt.rc('font', **font)

        print("Plotting...")

        image_type = self.project_name

        columns = self.df.columns.values
        indexes = self.df.index.values
        distance_dict = {}
        # Create plot
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)

        if plot or barchart:
            for check1, index in enumerate(indexes):
                distance_dict[index] = {}
                for check2, column in enumerate(columns):
                    '''
                    here try to reduce the redundancy
                    by avoiding to check the same comparisons twice                
                    '''
                    if check2 >= check1 and check2 != check1:
                        matches = self.df.loc[index, column]
                        distances = [match.distance for match in matches][:top_matches]
                        distance_dict[index][column] = distances
        if plot:
            distance_of_first_kp = []
            for item in distance_dict:
                for sub_item in distance_dict[item]:
                    tot_distances = sum(distance_dict[item][sub_item][:top_matches])
                    label = f"{item}_{sub_item}"
                    distance_of_first_kp.append((tot_distances, label))
            distance_of_first_kp = sorted(distance_of_first_kp, key=lambda x: x[0])

            top_labels = {}
            for item in distance_of_first_kp[:top_comparisons]:
                #important: here the distances array is again assiged instead of the total distance
                split = item[1].split('_')
                index = int(split[0])
                column = int(split[1])
                top_labels[item[1]] = distance_dict[index][column]

            for item in distance_dict:
                for sub_item in distance_dict[item]:
                    label = f"{item}_{sub_item}"
                    try:
                        distances = top_labels[label]
                        ind = list(range(len(top_labels.keys())))
                        ax.plot(ind, distances, alpha=0.5, label=label)
                        ax.text(ind[-int(len(ind)/2)], distances[-int(len(distances)/2)], f'{label}')
                    except KeyError:
                        continue

            ax.set_ylabel(f'keypoint distance')
            ax.set_xlabel(f'top 20 keypoints per comparison')
            ax.set_title(f'{self.algorithm}: top 20 {image_type} image comparisons distance profiles')
            ax.set_xticks(ind[:top_comparisons])
            ax.set_xticklabels(ind[:top_comparisons])

        elif barchart:
            #list of tuples: tot_distances and corresponding labels
            data = []
            counter = 0
            for item in distance_dict:
                for sub_item in distance_dict[item]:
                    counter += 1
                    tot_distances = sum(distance_dict[item][sub_item][:top_matches])
                    labels = f"{item}_{sub_item}"
                    data.append((tot_distances, labels))

            ind = np.arange(counter)
            data = sorted(data, key=lambda x: x[0])

            tot_distances = []
            labels = []
            for element in data:
                tot_distances.append(element[0])
                labels.append(element[1])

            bar = ax.bar(ind[:top_comparisons], tot_distances[:top_comparisons])
            '''
            if the bars should be labeled
            with the exact values on top uncomment the code below
            '''
            ax.set_ylabel(f'summed up distance')
            ax.set_xlabel(f'top {top_matches} image comparison variations')
            ax.set_title(f'{self.algorithm}: total distance {image_type} images')
            ax.set_xticks(ind[:top_comparisons])
            ax.set_xticklabels(labels[:top_comparisons])

        elif score_plot:
            motive_filename = "similarity_matrix_motive_0.45_2019_07_05_SURF.pkl"
            noise_filename = "similarity_matrix_noise_0.45_2019_07_05_SURF.pkl"
            motive_df = pd.read_pickle(f"{path_pickle_similarity}{motive_filename}")
            motive_indexes = motive_df.index.values
            motive_columns = motive_df.columns.values
            noise_df = pd.read_pickle(f"{path_pickle_similarity}{noise_filename}")
            noise_indexes = noise_df.index.values
            noise_columns = noise_df.columns.values

            score_tuplelist_motive = []
            score_tuplelist_noise = []

            for index in motive_indexes:
                for column in motive_columns:
                    score = motive_df.loc[index, column]
                    if math.isnan(score):
                        score = 0
                    #include only positiv scores
                    if score != 0:
                        score_tuplelist_motive.append((index, column, score))

            for index in noise_indexes:
                for column in noise_columns:
                    score = noise_df.loc[index, column]
                    if math.isnan(score):
                        score = 0
                    #include only positiv scores
                    if score != 0:
                        score_tuplelist_noise.append((index, column, score))
            #sort scores
            score_tuplelist_motive = sorted(score_tuplelist_motive, reverse=True, key=lambda x: x[2])
            score_tuplelist_noise = sorted(score_tuplelist_noise, reverse=True, key=lambda x: x[2])
            #get labels, scores
            scores_motive = []
            scores_noise = []
            labels_motive = []
            labels_noise = []

            for tuple in score_tuplelist_motive:
                labels_motive.append(f"{tuple[0][3:]}_{tuple[1][3:]}")
                scores_motive.append(tuple[2])

            for tuple in score_tuplelist_noise:
                labels_noise.append(f"{tuple[0][3:]}_{tuple[1][3:]}")
                scores_noise.append(tuple[2])

            ind_motive = np.arange(len(score_tuplelist_motive))
            ind_noise = np.arange(len(score_tuplelist_noise))

            ax.bar(ind_motive, scores_motive, label='Motives') #[:top_comparisons]
            ax.bar(ind_noise, scores_noise, label='Noise')

            ax.set_ylabel(f'score')
            ax.set_xlabel(f'image comparison variations')
            ax.set_title(f'{self.algorithm}: calculated image comparison scores, threshold {self.threshold}')
            ax.set_xticks(ind_motive)
            ax.set_xticklabels(ind_motive)
            # plt.yscale('log')
            plt.legend()

        plt.show()

    def add_features(self):
        '''
        1. add the needed amount of new columns according
        to the length of the similarity matrix
        then add the scores in the appropriate fields
        :return:
        '''
        _columns = self.df_similarity.columns.values
        for index, row in self.df_similarity.iterrows():
            for column, element in zip(_columns, row):
                self.subset_df.at[index, column] = element
        '''
        missing images have to be handeled here
        metadata of media objects with missing images are included in the subset_df
        but are missing in the df_similarity since the images were not loaded in the first place
        the resulting NaN values have to be replaced to 0, otherwise the clustering will raise errors
        UPDATE: these rows where everything is NaN have to be excluded from clustering, because
        they will cause irrelevant clusters!
        '''
        #when reasigning the following expression again to self.subset_df (with inplace=False)
        #then only this subsection of the dataframe will be reasigned to the original.
        #Testing what happens if no reasign but with inplace=True.
        #fillna() doesn't work as intendend as soon as one enters a list of rows AND columns
        '''
        isnull checks for NaN, None -> missing values. Zeros will NOT be removed!
        Only checks last column since that is enough, if the value is NaN its image does not exist
        '''
        boolean_array_no_nan_rows = self.subset_df.iloc[:, -1].notnull()
        self.subset_df = self.subset_df[boolean_array_no_nan_rows]

path_IMAGES = "C:/Users/mhartman/Documents/100mDataset/wildkirchli_images"
path_IMAGES_test = "C:/Users/mhartman/Documents/100mDataset/wildkirchli_images_test"
path_IMAGES_motives = "C:/Users/mhartman/Documents/100mDataset/wildkirchli_images_motives"
path_IMAGES_noise = "C:/Users/mhartman/Documents/100mDataset/wildkirchli_images_noise"
path_pickle_similarity = "C:/Users/mhartman/Documents/100mDataset/df_similarity_pickles/"
# path_performance_log = "/home/debian/MotiveDetection/performance_log.txt"

# inst1 = ImageSimilarityAnalysis(path_IMAGES_motives, 'SURF', pickle=False)
