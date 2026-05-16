"""
Deep autoencoder for tabular anomaly detection (IoT-23 / unusual network activity).

Learns to reconstruct normal connection feature vectors; large reconstruction error
can indicate abnormal flows. Training happens in a separate script.

Architecture: encoder uses BatchNormalization + Dropout for regularisation so the
bottleneck is forced to learn a compact, generalisable representation of benign
traffic rather than memorising individual training samples.
"""

from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers


def build_autoencoder(input_dim: int, dropout_rate: float = 0.2) -> keras.Model:
    """
    Build and compile a regularised symmetrical dense autoencoder for tabular data.

    Regularisation strategy
    -----------------------
    * BatchNormalization after each encoder dense layer stabilises training and
      reduces sensitivity to input feature scale.
    * Dropout (encoder only) prevents co-adaptation of hidden units and improves
      generalisation to unseen benign traffic patterns.
    * The decoder has no dropout so reconstruction quality is not artificially
      degraded at inference time.

    Parameters
    ----------
    input_dim
        Number of input features per row (after scaling / one-hot encoding).
    dropout_rate
        Fraction of encoder units randomly zeroed per training step (default 0.2).

    Returns
    -------
    keras.Model
        Compiled model (Adam optimiser, mean squared error). Not fitted here.
    """
    if input_dim < 1:
        raise ValueError("input_dim must be a positive integer.")
    if not (0.0 <= dropout_rate < 1.0):
        raise ValueError("dropout_rate must be in [0, 1).")

    inputs = keras.Input(shape=(input_dim,), name="features")

    # Encoder: compress to bottleneck with batch normalisation + dropout
    x = layers.Dense(128, use_bias=False, name="enc_1")(inputs)
    x = layers.BatchNormalization(name="bn_1")(x)
    x = layers.Activation("relu", name="act_1")(x)
    x = layers.Dropout(dropout_rate, name="drop_1")(x)

    x = layers.Dense(64, use_bias=False, name="enc_2")(x)
    x = layers.BatchNormalization(name="bn_2")(x)
    x = layers.Activation("relu", name="act_2")(x)
    x = layers.Dropout(dropout_rate, name="drop_2")(x)

    x = layers.Dense(32, use_bias=False, name="enc_3")(x)
    x = layers.BatchNormalization(name="bn_3")(x)
    x = layers.Activation("relu", name="act_3")(x)

    bottleneck = layers.Dense(16, activation="relu", name="bottleneck")(x)

    # Decoder: mirror encoder widths, no dropout (clean reconstruction)
    x = layers.Dense(32, activation="relu", name="dec_1")(bottleneck)
    x = layers.Dense(64, activation="relu", name="dec_2")(x)
    x = layers.Dense(128, activation="relu", name="dec_3")(x)
    outputs = layers.Dense(input_dim, activation="linear", name="reconstruction")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="iot_tabular_autoencoder_v2")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
    )
    return model
