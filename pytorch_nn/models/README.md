resnet.py — релизация resnet-101 на pytorch

resnet-adam-vs-adabound.ipynb — сравнение обучения имлементации из resnet.py с Adam и c AdaBound

# Напоминание о делталях архитектуры ResNet
![Здесь должно быть изображение с архитектурой ResNet-101. Оно должжно быть в папке images_for_readme](../images_for_readme/ResNet-101_Architecture_half_size.png)

ResNet-101 включает в себя свертку conv1, макс пулинг и далее множество коллекций слоев convi. convi_x является bottleneck'ом. Bottlencek состоит из трех сверток: 1x1, 3x3, 1x1. Первая свертка понижает число выходных каналов, последняя повышает.
Помимо сверток Bottleneck имеет identity mapping (точная копия входа Bottleneck'а), который складывается с выходом последней свертки Bottleneck'а. В случае, когда число каналов identity mapping'a не совападает с числом каналов выхода последней свертки, перед складыванием с conv3 над identity mapping'ом производится свертка 1x1, приводящая его к необходимой размерности.

В conv1 размерность плоскости входного тензора уменьшается вдвое в связи с тем, что stride = 2. Перед conv2_1 производится даунсемплинг карты признаков (feature map) в 2 раза с помощью max pooling'а. Далее conv3_1, conv_4_1 и conv5_1 первая свертка bottleneck'а имеет stride = 2. Таким образом, ширина и высота сходного "изображения" сужаются в 32 раза перед тем как дойти до average pooling, который оставляет одно значение для каждого канала. Такой пулинг позволяет использовать входные данные произвольной размерности. Тем не менее, в связи с понижением размерности при проходе через сеть вход должен быть не менее 32 и, желательно, кратен 32 (иначе тензоры будут "обрезаться").