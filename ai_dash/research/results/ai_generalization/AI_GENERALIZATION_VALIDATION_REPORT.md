# AI Temporal Generalization and Correlated-Failure Report

## Evidence boundary

This is an additive post-lock diagnostic. The principal 8/3/3-day model,
classification threshold, scheduling threshold, and 630-run scheduler result
remain unchanged. No model in this study is allowed to replace the principal
model on the already-inspected held-out dates.

## Rolling-origin evaluation

Nine prospective-style folds are evaluated. In each fold, all model fitting uses
only earlier dates, the two immediately preceding dates choose that model's
safety threshold, and the next chronological date is evaluated once. Model
families are fixed in advance; this diagnostic does not select a new principal
model.

```
                  model  folds  mean_auroc  median_auroc  min_auroc  mean_auprc  median_auprc  min_auprc  mean_brier  mean_ece_10  folds_auroc_below_0_5
current_sensor_logistic      9    0.831328      0.998682   0.427310    0.893060      0.996614   0.552910    0.264508     0.302578                      1
            extra_trees      9    0.876846      0.945650   0.578804    0.919412      0.995344   0.649388    0.219549     0.263754                      0
 hist_gradient_boosting      9    0.787896      0.888801   0.374689    0.790513      0.967452   0.327187    0.226670     0.226842                      2
      temporal_logistic      9    0.752802      0.791197   0.090556    0.811311      0.985413   0.169237    0.226640     0.227445                      2
```

The fold-wise record is retained in `rolling_origin_metrics.csv`, including
poor-performing days. This directly quantifies temporal instability instead of
hiding it in a pooled score.

## Correlated sensor-group failure

The exact serialized locked current-sensor logistic model and its original
validation-selected threshold are loaded without refitting or reselection. All
feature channels for one room/group are then zeroed together on the original
held-out dates.

```
   group                                                        failed_sensors  sensor_count    auroc    auprc  sensitivity  specificity    brier   ece_10  delta_auroc  delta_auprc  delta_brier
    none                                                                                   0 0.748740 0.832280     1.000000     0.342940 0.314482 0.271896     0.000000     0.000000     0.000000
bathroom              bathroomLight;bathroomDoorLock;bathroomDoor;bathroomCarp             4 0.604823 0.706134     1.000000     0.343193 0.483124 0.443288    -0.143917    -0.126146     0.168642
 bedroom bedroomLight;bedroomDoorLock;bedroomDoor;bedroomCarp;bedTableLamp;bed             6 0.846245 0.855107     1.000000     0.355075 0.426206 0.434578     0.097505     0.022827     0.111724
 kitchen      oven;kitchenLight;kitchenDoorLock;kitchenDoor;kitchenCarp;fridge             6 0.748740 0.832280     1.000000     0.342940 0.314483 0.272148     0.000000     0.000000     0.000001
  office               officeLight;officeDoorLock;officeDoor;officeCarp;office             5 0.726672 0.817528     1.000000     0.343067 0.314641 0.275182    -0.022068    -0.014752     0.000158
  living                                       tv;livingLight;livingCarp;couch             4 0.696409 0.800180     1.000000     0.009228 0.314486 0.271794    -0.052331    -0.032100     0.000003
   entry                                                 mainDoorLock;mainDoor             2 0.748679 0.832251     1.000000     0.480217 0.304596 0.240704    -0.000061    -0.000029    -0.009886
   other                                                 wardrobe;hallwayLight             2 0.748760 0.832280     1.000000     0.342940 0.314493 0.271915     0.000020    -0.000000     0.000011
```

Largest grouped AUPRC loss: `bathroom`
(-0.126146). This is an observed failure dependence, not
a causal claim about the room or sensors.

## Duplicate-timestamp sensitivity

```
                      subset     n  excluded    auroc    auprc  sensitivity  specificity  precision       f1    brier   ece_10  diagnostic_only_after_principal_test_lock
            all_test_samples 20670         0 0.748740 0.832280     1.000000     0.342940   0.710531 0.830772 0.314482 0.271896                                       True
exclude_duplicate_timestamps 20670         0 0.748740 0.832280     1.000000     0.342940   0.710531 0.830772 0.314482 0.271896                                       True
```

This check does not rewrite source labels or choose a preferred dataset version;
it reports how the locked model behaves when duplicate timestamps are excluded
from scoring.
