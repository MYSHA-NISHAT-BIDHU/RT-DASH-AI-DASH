#ifndef RTDASH_PORTABLE_LOGISTIC_MODEL_H
#define RTDASH_PORTABLE_LOGISTIC_MODEL_H

#include <math.h>
#include <stddef.h>

#define RTDASH_AI_FEATURE_COUNT 29u

/* 0: sensor_current__wardrobe */
/* 1: sensor_current__tv */
/* 2: sensor_current__oven */
/* 3: sensor_current__officeLight */
/* 4: sensor_current__officeDoorLock */
/* 5: sensor_current__officeDoor */
/* 6: sensor_current__officeCarp */
/* 7: sensor_current__office */
/* 8: sensor_current__mainDoorLock */
/* 9: sensor_current__mainDoor */
/* 10: sensor_current__livingLight */
/* 11: sensor_current__livingCarp */
/* 12: sensor_current__kitchenLight */
/* 13: sensor_current__kitchenDoorLock */
/* 14: sensor_current__kitchenDoor */
/* 15: sensor_current__kitchenCarp */
/* 16: sensor_current__hallwayLight */
/* 17: sensor_current__fridge */
/* 18: sensor_current__couch */
/* 19: sensor_current__bedroomLight */
/* 20: sensor_current__bedroomDoorLock */
/* 21: sensor_current__bedroomDoor */
/* 22: sensor_current__bedroomCarp */
/* 23: sensor_current__bedTableLamp */
/* 24: sensor_current__bed */
/* 25: sensor_current__bathroomLight */
/* 26: sensor_current__bathroomDoorLock */
/* 27: sensor_current__bathroomDoor */
/* 28: sensor_current__bathroomCarp */

static const double RTDASH_AI_MEAN[RTDASH_AI_FEATURE_COUNT] = {
    0.078791508617821249,
    0.26009848938577229,
    0.10494443335329739,
    0.0031277034670925668,
    0,
    0.065448858720968922,
    0.0053570240234245029,
    0,
    0.93902641911226459,
    0.060657483196912228,
    0.46664337525786914,
    0.26236108338324349,
    0.10743994143874359,
    0,
    0.095228588540626866,
    0.034837292872828905,
    0.061439409063685363,
    0.009549477606974114,
    0.24718839422373062,
    0.14532175417581686,
    0.12818593198908632,
    0.3010580954282292,
    0.48951886604112599,
    0.02510481133958874,
    0.51117987622279892,
    0.14776735209955413,
    0.1198842084248353,
    0.018882677846542888,
    0.15387302854861248
};
static const double RTDASH_AI_SCALE[RTDASH_AI_FEATURE_COUNT] = {
    0.26941307835283179,
    0.43868811837683919,
    0.30648180902208982,
    0.055838346484423276,
    1,
    0.24731620572273777,
    0.0729953855872887,
    1,
    0.23928184912663603,
    0.23870096968619237,
    0.49888609480102031,
    0.43991788473442889,
    0.30967176239105643,
    1,
    0.29353041488947418,
    0.18336754319704909,
    0.2401345624386263,
    0.097253715015972589,
    0.43137720383073574,
    0.35242494511467309,
    0.33429672273173078,
    0.45871790743915425,
    0.49989013376034547,
    0.1564434715390591,
    0.49987499474132824,
    0.35486921781557856,
    0.32482608422844672,
    0.13611069878553475,
    0.36082699404824237
};
static const double RTDASH_AI_WEIGHT[RTDASH_AI_FEATURE_COUNT] = {
    -0.46579599857564907,
    0.076935897472616963,
    -0.7554384746628976,
    -0.15450887661188081,
    0,
    1.2829018475798049,
    -0.22852682503209346,
    0,
    0.16333540981971226,
    0.13023261539179035,
    -1.8522309409883626,
    -0.72237852467369812,
    -0.47449720056421069,
    0,
    0.77484356198664606,
    -0.54527430482034889,
    0.02613964888945506,
    -0.33240445745196318,
    0.56210131709288136,
    0.49193667875007452,
    -3.1372932144073618,
    0.91312035670182157,
    1.9658066918030872,
    -1.6475125475449357,
    2.0921862224263941,
    0.32499793830140433,
    3.1786572830302573,
    -0.49361442799552979,
    0.8692360296036119
};
static const double RTDASH_AI_INTERCEPT = -4.4131319858736466;

static inline double rtdash_ai_risk(const double *features, size_t length) {
    if (features == NULL || length != RTDASH_AI_FEATURE_COUNT) return -1.0;
    double score = RTDASH_AI_INTERCEPT;
    for (size_t i = 0; i < RTDASH_AI_FEATURE_COUNT; ++i) {
        score += ((features[i] - RTDASH_AI_MEAN[i]) / RTDASH_AI_SCALE[i])
                 * RTDASH_AI_WEIGHT[i];
    }
    if (score >= 0.0) return 1.0 / (1.0 + exp(-score));
    const double exponential = exp(score);
    return exponential / (1.0 + exponential);
}

#endif
