import copy
import functools

import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras import layers
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.layers import *
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import SGD, Adam, RMSprop
from tensorflow.keras.utils import to_categorical

from kerastuner.applications.hyperception.blocks import sep_conv, conv, dense, residual
from kerastuner.applications.hyperception.hparams import default_fixed_hparams, default_hparams


def hyperception(input_shape, num_classes, **hparams):
    """ Returns a wrapper around a hyperception function which provides the
    specified shape, number of output classes, and hyperparameters.

    Args:
        input_shape (tuple):  Shape of the input image.
        num_classes (int): Number of output classes.
        hparams (**dictionary): Hyperparameters to the Hyperception model.

    Returns:
        A wrapped hyperception function.
    """

    return functools.partial(_hyperception, input_shape, num_classes, **hparams)


def hyperception_single_fn(input_shape, num_classes, **hparams):
    """ Returns a wrapper around a hyperception_single function which provides the
    specified shape, number of output classes, and hyperparameters.

    Args:
        input_shape (tuple):  Shape of the input image.
        num_classes (int): Number of output classes.
        hparams (**dictionary): Hyperparameters to the Hyperception model.

    Returns:
        A wrapped hyperception_single function.
    """

    return functools.partial(_hyperception_single, input_shape, num_classes, **hparams)


def hyperception_single_model(input_shape, num_classes, **hparams):
    model_fn = hyperception_single_fn(input_shape, num_classes, **hparams)
    print(model_fn)
    i = model_fn()
    print(i)
    return i


def _hyperception(input_shape, num_classes, **hparams):
    """
    Implementation of a hypertunable adaptation of Xception.    
    """
    hp = {}
    hp.update(default_hparams(input_shape, num_classes))
    if hparams:
        hp.update(hparams)

    ### Parameters ###

    # [general]
    kernel_size = hp["kernel_size"]

    initial_strides = hp["initial_strides"]
    activation = hp["activation"]

    optimizer = hp["optimizer"]

    # [entry flow]

    # -conv2d
    conv2d_num_filters = hp["conv2d_num_filters"]

    # seprarable block > not an exact match to the paper
    sep_num_filters = hp["sep_num_filters"]

    # [Middle Flow]
    num_residual_blocks = hp["num_residual_blocks"]

    # [Exit Flow]
    dense_merge_type = hp["dense_merge_type"]
    num_dense_layers = hp["num_dense_layers"]
    dropout_rate = hp["dropout_rate"]
    dense_use_bn = hp["dense_use_bn"]

    ### Model ###
    # input
    inputs = keras.Input(shape=input_shape)
    x = inputs

    # Initial conv2d
    dims = conv2d_num_filters
    x = conv(x, dims, kernel_size=kernel_size, activation=activation,
             strides=initial_strides)

    # separable convs
    dims = sep_num_filters
    for _ in range(num_residual_blocks):
        x = residual(x, dims, activation=activation, max_pooling=False)

    # Exit
    dims *= 2
    x = residual(x, dims, activation=activation, max_pooling=True)

    if dense_merge_type == 'flatten':
        x = layers.Flatten()(x)
    elif dense_merge_type == "avg":
        x = layers.GlobalAveragePooling2D()(x)
    else:
        x = layers.GlobalMaxPooling2D()(x)

    # Dense
    for _ in range(num_dense_layers):
        x = dense(x, num_classes, activation=activation, batchnorm=dense_use_bn,
                  dropout_rate=dropout_rate)
    output = layers.Dense(num_classes, activation='softmax')(x)
    model = keras.Model(inputs, output)

    if optimizer == "adam":
        lr = hp["learning_rate"]
        optimizer = Adam(lr=lr)
    elif optimizer == "sgd":
        lr = hp["learning_rate"]
        momentum = hp["momentum"]
        decay = hp["learning_rate_decay"]
        optimizer = SGD(lr=lr, momentum=momentum, decay=decay)
    elif optimizer == "rmsprop":
        lr = hp["learning_rate"]
        decay = hp["learning_rate_decay"]
        optimizer = RMSprop(lr=lr, decay=decay)
    else:
        raise ValueError("Optimizer '%s' not supported", optimizer)

    model.compile(
        optimizer=optimizer,
        loss='categorical_crossentropy',
        metrics=['accuracy'])

    return model


def _hyperception_single(
        input_shape,
        num_classes,
        mode="full",
        **hparams):
    """ Model fn which uses a single value for the hyper parameters """

    hp = default_fixed_hparams(input_shape, num_classes)
    hp.update(hparams)
    return _hyperception(input_shape=input_shape, num_classes=num_classes, **hp)