import os
import tqdm

import skimage
import skimage.data
import skimage.transform

import numpy as np

import tensorflow as tf

import piecewisecrf.helpers.io as io
import piecewisecrf.datasets.cityscapes.prefs as prefs
import piecewisecrf.datasets.helpers.pairwise_label_generator as label_gen

FLAGS = prefs.flags.FLAGS


def _int64_feature(value):
    """Wrapper for inserting int64 features into Example proto."""
    if not isinstance(value, list):
        value = [value]
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def _bytes_feature(value):
    """Wrapper for inserting bytes features into Example proto."""
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def prepare_dataset(name):
    print('Prepairing {} dataset'.format(name))
    root_dir = os.path.join(FLAGS.dataset_dir, name)
    root_dir = os.path.join(root_dir, '{}x{}'.format(FLAGS.img_width, FLAGS.img_height))
    img_dir = os.path.join(root_dir, 'img')
    gt_dir = os.path.join(root_dir, 'gt_bin')

    save_dir = os.path.join(FLAGS.save_dir, name)
    save_dir = os.path.join(save_dir, '{}x{}'.format(FLAGS.img_width, FLAGS.img_height))
    save_dir = os.path.join(save_dir, 'tfrecords')

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    rgb_means = [FLAGS.r_mean, FLAGS.g_mean, FLAGS.b_mean]

    for img_name in tqdm.tqdm(next(os.walk(img_dir))[2]):
        img_prefix = img_name[0:img_name.index('.')]
        rgb = skimage.data.load(os.path.join(img_dir, img_name))
        rgb = rgb.astype(np.float32)

        # likely not needed - to turn off set zero mean values
        for c in range(3):
            rgb[:, :, c] -= rgb_means[c]

        labels = io.load_nparray_from_bin_file(os.path.join(gt_dir, '{}.bin'.format(img_prefix)), np.uint8)
        # don't know if this resizing is okay - TODO
        subslampled_size = (labels.shape[0] / FLAGS.subsample_factor * FLAGS.max_scale,
                            labels.shape[1] / FLAGS.subsample_factor * FLAGS.max_scale)
        labels = skimage.transform.resize(labels, subslampled_size, order=0, preserve_range=True)
        labels = labels.astype(np.int32)  # likely not needed
        labels_pairwise_surrounding = label_gen.generate_pairwise_labels(labels,
                                                                         label_gen.get_indices_surrounding,
                                                                         FLAGS.num_classes)
        labels_pairwise_above_below = label_gen.generate_pairwise_labels(labels,
                                                                         label_gen.get_indices_above_below,
                                                                         FLAGS.num_classes)

        rows = rgb.shape[0]
        cols = rgb.shape[1]
        depth = rgb.shape[2]

        filename = os.path.join(save_dir, '{}.tfrecords'.format(img_prefix))
        writer = tf.python_io.TFRecordWriter(filename)

        rgb_raw = rgb.tostring()
        labels_raw = labels.tostring()
        labels_pairwise_surrounding_raw = labels_pairwise_surrounding.tostring()
        labels_pairwise_above_below_raw = labels_pairwise_above_below.tostring()
        example = tf.train.Example(features=tf.train.Features(feature={
            'height': _int64_feature(rows),
            'width': _int64_feature(cols),
            'depth': _int64_feature(depth),
            'img_name': _bytes_feature(img_prefix.encode()),
            'rgb': _bytes_feature(rgb_raw),
            'labels_unary': _bytes_feature(labels_raw),
            'labels_binary_surrounding': _bytes_feature(labels_pairwise_surrounding_raw),
            'labels_binary_above_below': _bytes_feature(labels_pairwise_above_below_raw)}))
        writer.write(example.SerializeToString())
        writer.close()


def main(argv):
    prepare_dataset('train_val')
    prepare_dataset('train_train')
    prepare_dataset('val')


if __name__ == '__main__':
    tf.app.run()
