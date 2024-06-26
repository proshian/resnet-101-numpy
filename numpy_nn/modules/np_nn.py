import numpy as np
import itertools
from typing import List, Tuple

class Module:
    """
    Base class for any neural network component. It can be a layer,
    an activation function, a subnetwork, etc. 
    """
    def __init__(self):
        pass
    
    def forward(self, input_: np.ndarray) -> np.ndarray:
        raise NotImplementedError
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        raise NotImplementedError
    
    def get_trainable_layers(self) -> List['TrainableLayer']:
        # ! May be add Layer (or UntrainableLayer) class and mode this version
        # ! of get_trainable_layers to it. And here raise NotImplementedError
        return []
    
    training: bool = True
    
    def train(self):
        self.training = True
        for layer in self.get_trainable_layers():
            # ! This case is only for layers (not for bigger components)
            if self == layer:
                continue
            layer.train()
    
    def eval(self):
        self.training = False
        for layer in self.get_trainable_layers():
            # ! This case is only for layers (not for bigger components)
            if self == layer:
                continue
            layer.eval()
    
    def is_equal(self, other, check_gradien_equity = True):
        for self_layer, other_layer in zip(self.get_trainable_layers(), other.get_trainable_layers()):
            self_pgi_list = self_layer.get_parameters_and_gradients_and_ids()
            other_pgi_list = other_layer.get_parameters_and_gradients_and_ids()
            for (self_p, self_g, self_id), (other_p, other_g, other_id) in zip(self_pgi_list, other_pgi_list):
                if not np.all(self_p == other_p):
                    return False
                if check_gradien_equity:
                    if ((self_g or other_g) is None) and ((self_g and other_g) is not None):
                        return False
                    if not np.all(self_g == other_g):
                        return False
        return True
    

class TrainableLayer(Module):
    id_iter = itertools.count()

    def __init__(self):
        # id is used to identify layer's weights and bias in an optimizer.

        # There are supposed to be no layers with same id within a run.
        # However if we load model from a previous run somehow, there may
        # be a situation when two models have layers with same ids. It can
        # be an issue in theory if one optimizer optimizes weights of two
        # models at the same time. However, I'm not sure that it may happen.
        # Another potantial danger is adding new layers to a model loaded
        # from a previous run. In this situation it one model can have
        # several layers with same id. This will lead to problems
        # during training. 
        
        self.id = next(TrainableLayer.id_iter)
    
    def get_parameters_and_gradients_and_ids(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        raise NotImplementedError
    
    def get_trainable_layers(self) -> List['TrainableLayer']:
        return [self]

class FullyConnectedLayer(TrainableLayer):
    def __init__(self, n_input_neurons: int, n_output_neurons: int):
        # ! id is set in TrainableLayer class
        super().__init__()
        self.weights = np.random.randn(n_input_neurons, n_output_neurons) * 0.01
        self.bias = np.random.randn(1, n_output_neurons) * 0.01
        self.weights_gradient = None
        self.bias_gradient = None
    
    def forward(self, input_: np.ndarray) -> np.ndarray:
        """
        input_ is a 2D array with shape (batch_size, n_input_neurons)
        output is a 2D array with shape (batch_size, n_output_neurons)
        """
        self.input_ = input_
        self.output = np.dot(self.input_, self.weights) + self.bias
        return self.output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        # The math explanation: https://web.eecs.umich.edu/~justincj/teaching/eecs442/notes/linear-backprop.html
        input_gradient = np.dot(output_gradient, self.weights.T)
        self.weights_gradient = np.dot(self.input_.T, output_gradient)
        self.bias_gradient = np.sum(output_gradient, axis=0, keepdims=True)
        return input_gradient
    
    #! Maybe move to super class
    def get_W_and_b_ids(self) -> Tuple[str, str]:
        weights_id = f"dW{self.id}"
        bias_id = f"db{self.id}"
        return weights_id, bias_id

    def get_parameters_and_gradients_and_ids(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        weights_id, bias_id = self.get_W_and_b_ids()
        return [(self.weights, self.weights_gradient, weights_id), (self.bias, self.bias_gradient, bias_id)]


class Conv2dWithLoops(TrainableLayer):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int,
                 stride: int = 1, padding: int = 0, bias: bool = True):
        super(Conv2dWithLoops, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.bias = bias
        self.weights_gradient = None
        self.bias_gradient = None

        # out_channels is the number of filters and in_channels, kernel_size, kernel_size are the shape of the filter
        self.weights = np.random.randn(out_channels, in_channels, kernel_size, kernel_size) * 0.01
        if self.bias:
            self.bias = np.random.randn(out_channels) * 0.01
            # ! i think an alternative is np.random.randn(out_channels, 1, 1, 1) * 0.01
        else:
            self.bias = None
    
    def _get_padded_input(self, input_: np.ndarray) -> np.ndarray:
        batch_size, in_channels, height, width = input_.shape
        padded_height = height + 2 * self.padding
        padded_width = width + 2 * self.padding
        padded_input = np.zeros((batch_size, in_channels, padded_height, padded_width))
        padded_input[:, :, self.padding:self.padding+height, self.padding:self.padding+width] = input_
        return padded_input
    
    # ! May be make convolution a separate function and call it in forward and backward
    def forward(self, input_: np.ndarray) -> np.ndarray:
        """
        input_ is a 4D array with shape (batch_size, in_channels, height, width)
        """
        self.input_ = input_
        batch_size, _, height, width = input_.shape
        padded_input = self._get_padded_input(input_)
        padded_height = height + 2 * self.padding
        padded_width = width + 2 * self.padding
        out_height = (padded_height - self.kernel_size) // self.stride + 1
        out_width = (padded_width - self.kernel_size) // self.stride + 1
        output = np.empty((batch_size, self.out_channels, out_height, out_width))
        # oci stands for output channel index
        for oci in range(self.out_channels):
            for h in range(out_height):
                for w in range(out_width):
                    output[:, oci, h, w] = np.sum(
                        self.weights[oci] * padded_input[:, :, h*self.stride:h*self.stride+self.kernel_size, w*self.stride:w*self.stride+self.kernel_size],
                        axis=(1, 2, 3))
            if self.bias is not None:
                output[:, oci] += self.bias[oci]
        return output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        """
        output_gradient is a 4D array with shape (batch_size, out_channels, out_height, out_width)
        """
        batch_size, out_channels, out_height, out_width = output_gradient.shape
        _, _, height, width = self.input_.shape
        padded_input = self._get_padded_input(self.input_)
        input_gradient = np.zeros_like(padded_input)
        self.weights_gradient = np.zeros(self.weights.shape)
        if self.bias is not None:
            self.bias_gradient = np.zeros(self.bias.shape)
        # bi stands for batch index
        for bi in range(batch_size):
            for oci in range(out_channels):
                for h in range(out_height):
                    for w in range(out_width):
                        # h_start is row position of the first element of the kernel
                        h_start = h*self.stride 
                        # h_end is row position of the last element of the kernel
                        h_end = h*self.stride+self.kernel_size
                        # w_start is column position of the first element of the kernel
                        w_start = w*self.stride
                        # w_end is column position of the last element of the kernel
                        w_end = w*self.stride+self.kernel_size
                        input_gradient[bi, :, h_start:h_end, w_start:w_end] += (
                            self.weights[oci] * output_gradient[bi, oci, h, w])
                        self.weights_gradient[oci] += (
                            padded_input[bi, :, h_start:h_end, w_start:w_end] *
                            output_gradient[bi, oci, h, w])
                        if self.bias is not None:
                            self.bias_gradient[oci] += output_gradient[bi, oci, h, w]
        return input_gradient[:, :, self.padding:self.padding+height, self.padding:self.padding+width]

    def get_W_and_b_ids(self) -> Tuple[str, str]:
        weights_id = f"dW{self.id}"
        bias_id = f"db{self.id}"
        return weights_id, bias_id
    
    def get_parameters_and_gradients_and_ids(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        parameters_and_gradients_and_ids = []
        weights_id, bias_id = self.get_W_and_b_ids()
        parameters_and_gradients_and_ids.append((self.weights, self.weights_gradient, weights_id))
        if self.bias is not None:
            parameters_and_gradients_and_ids.append((self.bias, self.bias_gradient, bias_id))
        return parameters_and_gradients_and_ids



class Conv2d(TrainableLayer):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int,
                 stride: int = 1, padding: int = 0, bias: bool = True):
        super(Conv2d, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.bias = bias
        self.weights_gradient = None
        self.bias_gradient = None

        # out_channels is the number of filters and in_channels, kernel_size, kernel_size are the shape of the filter
        self.weights = np.random.randn(out_channels, in_channels, kernel_size, kernel_size) * 0.01
        if self.bias:
            self.bias = np.random.randn(out_channels) * 0.01
        else:
            self.bias = None
    
    def _get_padded_input(self, input_: np.ndarray) -> np.ndarray:
        batch_size, in_channels, height, width = input_.shape
        padded_height = height + 2 * self.padding
        padded_width = width + 2 * self.padding
        padded_input = np.zeros((batch_size, in_channels, padded_height, padded_width))
        padded_input[:, :, self.padding:self.padding+height, self.padding:self.padding+width] = input_
        return padded_input
    
    # ! May be it would be a nice idea to make the conversion to "regular"
    # shape and make a getter. So that users won't be scared :)

    @staticmethod
    def _convert_bias(bias):
        return bias.reshape(-1, 1)

    @staticmethod
    def _convert_weights(weights):
        # We need to convert weights to a 2d matrix where rows are separate
        # flattened filters of initial weights tensor
        # ! not sure if I do it inplace.
        # ! If I will implement the convolution with matrix multiplication
        # ! I think I should initialize weights as a 2d matrix insted of
        # ! a 4d tensor and never call this method

        # ! This method will only be called to compare two convolution
        # ! implementations. Specifically to initialize the weights
        # ! with the same values as torch implementation and
        # ! implementation with loops 

        # ! Those "for loops" are better then naive implementation since the 
        # ! conversion is performed a single time while the matrix
        # ! multiplication is performed on every step of training 
        flattened_filters = []
        for filter in weights:
            flattened_filters.append(filter.reshape(1, -1))
        coverted_weights = np.concatenate(flattened_filters, axis = 0)
        return coverted_weights
    
    def _convert_input(self, padded_input: np.ndarray) -> np.ndarray:
        converted_input = None

        # I will refer to feature maps as images
        # The columns of a converted image are concatenated horizontally
        # The separate images are concatenated horizontally too.
        # Thus we will append all columns of all images in one list
        # that will be concatenated in the end

        _, _, height, width = padded_input.shape
        output_height = (height - self.kernel_size) // self.stride + 1
        output_width = (width - self.kernel_size) // self.stride + 1

        image_lines = []
        for image in padded_input:
            # the indexes are as if we walk through the output tensor in "regular" conv implementation
            for r in range(output_height):
                for c in range(output_width):
                    image_lines.append(
                        image[:, r*self.stride:r*self.stride+self.kernel_size, c*self.stride:c*self.stride+self.kernel_size].reshape(-1, 1))
        converted_input = np.concatenate(image_lines, axis = 1)
        
        # ! Below is a test that checks if converted_input has a proper shape 
        # print("converted_input.shape = ", converted_input.shape)
        # expected_shape = (input_.shape[1] * self.kernel_size * self.kernel_size, input_.shape[0] * output_height * output_width)
        # print(expected_shape)
        # print(converted_input.shape == expected_shape)

        return converted_input

    
    def _restore_input_gradient(self, converted_input: np.ndarray, padded_input_shape) -> np.ndarray:
        """
        If we needed to restore the input after _convert_input was applied we would need
        to use a function exactly like this but padded_input[b_i, :, r_start:r_end, c_start:c_end]
        would be replaced by converted_input[:, image_line_index].reshape(in_channels, kernel_size, kernel_size)
        insted of accumulating.
        """
        # This method restores input after _convert_input was applied
        # It is used in backward to restore the input_gradient to proper shape 
        padded_input = np.zeros(padded_input_shape)
        batch_size, _, height, width = padded_input_shape
        output_height = (height - self.kernel_size) // self.stride + 1
        output_width = (width - self.kernel_size) // self.stride + 1
        
        image_line_index = 0
        for b_i in range(batch_size):
            for r in range(output_height):
                for c in range(output_width):
                    # r_start is row position of the first element of the kernel
                    r_start = r*self.stride 
                    # r_end is row position of the last element of the kernel
                    r_end = r*self.stride+self.kernel_size
                    # c_start is column position of the first element of the kernel
                    c_start = c*self.stride
                    # c_end is column position of the last element of the kernel
                    c_end = c*self.stride+self.kernel_size
                    padded_input[b_i, :, r_start:r_end, c_start:c_end] += converted_input[:, image_line_index].reshape(-1, self.kernel_size, self.kernel_size)
                    image_line_index += 1
        return padded_input
    


    def forward(self, input_: np.ndarray) -> np.ndarray:
        # Used this explanation https://stepik.org/lesson/309343/step/7?unit=291492
        self.input_ = input_
        batch_size, _, height, width = input_.shape
        padded_input = self._get_padded_input(input_)
        padded_height = height + 2 * self.padding
        padded_width = width + 2 * self.padding
        out_height = (padded_height - self.kernel_size) // self.stride + 1
        out_width = (padded_width - self.kernel_size) // self.stride + 1

        converted_weights = self._convert_weights(self.weights)
        # self.converted_weights = converted_weights
        if self.bias is not None:
            converted_bias = self._convert_bias(self.bias)
        # ! We can pass out_height and out_width to _convert_input.
        converted_input = self._convert_input(padded_input)
        self.converted_input = converted_input
        conv2d_out = converted_weights @ converted_input
        if self.bias is not None:
            conv2d_out += converted_bias
        # print("conv2d_out.shape before reshape and transpose = ", conv2d_out.shape)
        return conv2d_out.reshape(self.out_channels, batch_size, out_height, out_width).transpose(1, 0, 2, 3)
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        input_gradient = self.backward_as_matrix_multiplication(output_gradient)
        self.converted_input = None  # free memory
        return input_gradient

    def backward_as_matrix_multiplication(self, output_gradient: np.ndarray) -> np.ndarray:
        output_gradient_converted = output_gradient.transpose(1, 0, 2, 3).reshape(self.out_channels, -1)


        self.weights_gradient = output_gradient_converted @ self.converted_input.T
        self.weights_gradient = self.weights_gradient.reshape(self.weights.shape)

        if self.bias is not None:
            self.bias_gradient = output_gradient_converted.sum(axis = 1).reshape(self.bias.shape)


        converted_weights = self._convert_weights(self.weights)
        input_gradient = converted_weights.T @ output_gradient_converted

        batch_size, n_input_channels, input_h, input_w = self.input_.shape
        padded_input_shape = (batch_size, n_input_channels,
            input_h + 2 * self.padding, input_w + 2 * self.padding)

        input_gradient = self._restore_input_gradient(input_gradient, padded_input_shape)

        return input_gradient[:, :, self.padding:self.padding+input_h, self.padding:self.padding+input_w]

    
    def get_W_and_b_ids(self) -> Tuple[str, str]:
        weights_id = f"dW{self.id}"
        bias_id = f"db{self.id}"
        return weights_id, bias_id
    
    def get_parameters_and_gradients_and_ids(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        parameters_and_gradients_and_ids = []
        weights_id, bias_id = self.get_W_and_b_ids()
        parameters_and_gradients_and_ids.append((self.weights, self.weights_gradient, weights_id))
        if self.bias is not None:
            parameters_and_gradients_and_ids.append((self.bias, self.bias_gradient, bias_id))
        return parameters_and_gradients_and_ids


class MaxPool2d(Module):
    # ! May be use inheritance or a global function to perform padding
    def __init__(self, kernel_size: int, stride: int, padding: int = 0, use_neg_inf_for_padding: bool = True):
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self._use_neg_inf_for_padding = use_neg_inf_for_padding
    
    def _get_padded_input(self, input_: np.ndarray) -> np.ndarray:
        batch_size, n_channels, height, width = input_.shape
        padded_shape = (batch_size, n_channels, height + 2*self.padding, width + 2*self.padding)

        if self._use_neg_inf_for_padding:
            padded_input = np.full(padded_shape, -np.inf)  #.astype(input_.dtype)
        else:
            padded_input = np.zeros(padded_shape)  #.astype(input_.dtype)
        padded_input[:, :, self.padding:self.padding+height, self.padding:self.padding+width] = input_
        return padded_input

    def forward(self, input_: np.ndarray) -> np.ndarray:
        self.input_ = input_
        padded_input = self._get_padded_input(input_)
        batch_size, n_channels, height, width = padded_input.shape
        out_height = (height - self.kernel_size) // self.stride + 1
        out_width = (width - self.kernel_size) // self.stride + 1
        output = np.zeros((batch_size, n_channels, out_height, out_width))
        for bi in range(batch_size):
            for oci in range(n_channels):
                for h in range(out_height):
                    for w in range(out_width):
                        h_start = h*self.stride
                        h_end = h*self.stride+self.kernel_size
                        w_start = w*self.stride
                        w_end = w*self.stride+self.kernel_size
                        output[bi, oci, h, w] = np.max(padded_input[bi, oci, h_start:h_end, w_start:w_end])
        return output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        padded_input = self._get_padded_input(self.input_)
        batch_size, n_channels,height, width = self.input_.shape
        out_height = (height + 2*self.padding - self.kernel_size) // self.stride + 1
        out_width = (width + 2*self.padding - self.kernel_size) // self.stride + 1
        input_gradient = np.zeros_like(padded_input)
        for bi in range(batch_size):
            for oci in range(n_channels):
                for h in range(out_height):
                    for w in range(out_width):
                        h_start = h*self.stride
                        h_end = h*self.stride+self.kernel_size
                        w_start = w*self.stride
                        w_end = w*self.stride+self.kernel_size
                        window = padded_input[bi, oci, h_start:h_end, w_start:w_end]
                        max_value = np.max(window)
                        mask = (window == max_value)
                        input_gradient[bi, oci, h_start:h_end, w_start:w_end] += mask * output_gradient[bi, oci, h, w]
                        
        return input_gradient[:, :, self.padding:self.padding+height, self.padding:self.padding+width]


class GlobalAveragePooling2D:
    def __init__(self):
        self.input_shape = None

    def forward(self, input_):
        self.input_shape = input_.shape
        return np.mean(input_, axis=(2, 3))
    
    def backward(self, d_J_d_out):
        d_out_d_in = np.ones(self.input_shape) / np.prod(self.input_shape[2:])
        d_J_d_out = d_J_d_out[:, :, np.newaxis, np.newaxis]
        return d_out_d_in * d_J_d_out
    

class BatchNormalization2d(TrainableLayer):
    """
    Args:
        n_channels: number of channels in the input
        momentum: momentum for running mean and variance (coeff for exponential moving average)
            Note: statistics are updated like this:
                running_mean = (1 - momentum) * running_mean + momentum * mean, which is not
                typical for momentum. This is done to be consistent with PyTorch.
                So the possible values for momentum are in the range (0, 1)
                # ! Not sure is 1 is allowed but 0 is not.
    """
    def __init__(self, n_channels: int, momentum: float = 0.1, eps = 1e-5):
        super(BatchNormalization2d, self).__init__()
        self.n_channels = n_channels
        self.gamma = np.ones((1, n_channels, 1, 1))  # new variance after normalization
        self.beta = np.zeros((1, n_channels, 1, 1))  # new mean after normalization
        # Added mean and var initialization to avoid a rare situation
        # where the model is not traind but the flag self.train is set to False
        self.running_mean = np.zeros((1, n_channels, 1, 1))
        self.running_var = np.ones((1, n_channels, 1, 1))
        self.eps = eps
        self.gamma_gradient = None
        self.beta_gradient = None
        self.momentum = momentum
        self.num_batches_trained_on = 0
    
    def update_running_mean_and_var(self):
        # This is one of the ways to cope with bias towards first value (bias correction)
        # if np.equal(self.running_mean, 0).all():
        #     self.running_mean = self.mean
        #     self.running_var = self.var
        #     return
        self.running_mean = self.momentum * self.mean\
            + (1 - self.momentum) * self.running_mean
        
        # afaik, pytorch uses unbiased running variance
        # May be it's because running_mean is averaging over a relatively
        # small number of elements and we need Bessel's correction.
        n = np.prod(self.input_.shape)/self.n_channels
        self.running_var = self.momentum * self.var * n / (n-1)\
            + (1 - self.momentum) * self.running_var
        

        # ! В официальном торче батчнормализация сделана на cpp. Код вот:
        # https://github.com/pytorch/pytorch/blob/420b37f3c67950ed93cd8aa7a12e673fcfc5567b/aten/src/ATen/native/Normalization.cpp#L61-L126
        # Однако, есть реализация, сделанная руками, которая по идее не должна отличаться. Она ниже.
        # Там же и тестирующий метод, который позвлит убедиться, стоит ли доверять этой имплементации.
        # https://github.com/ptrblck/pytorch_misc/blob/master/batch_norm_manual.py

        # Убрал, так как, насколько я понимаю, pytorch реализация не использует bias correction
        # ! возможно, нужно делать операции ниже не implace
        # # bias correction
        # self.running_mean /= self.momentum**(self.num_batches_trained_on + 1)
        # self.running_var /= self.momentum**(self.num_batches_trained_on + 1)
        # self.num_batches_trained_on += 1

    def forward(self, input_: np.ndarray) -> np.ndarray:
        self.input_ = input_
        # In the training phase, we use the mean and std of the current batch
        # In the testing phase, we use the exponential moving average
        # of the mean and std across all batches
        if self.training:
            self.mean = input_.mean(axis = (0, 2, 3), keepdims = True)
            self.var = input_.var(axis = (0, 2, 3), keepdims = True, ddof = 0)
            self.update_running_mean_and_var()
        else:
            self.mean = self.running_mean
            self.var = self.running_var
        std = np.sqrt(self.var + self.eps).reshape(1, self.n_channels, 1, 1)
        self.norm_input = (input_ - self.mean) / std
        output = self.gamma * self.norm_input + self.beta
        return output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        # The formulas are taken from: https://neerc.ifmo.ru/wiki/index.php?title=Batch-normalization
        self.beta_gradient = np.sum(
            output_gradient, axis = (0, 2, 3), keepdims=True)
        
        self.gamma_gradient = np.sum(
            output_gradient * self.norm_input,
            axis = (0, 2, 3),
            keepdims=True)

        norm_input_gradient = output_gradient * self.gamma

        prod = norm_input_gradient * (self.input_ - self.mean)
        sum_ = np.sum(prod, axis = (0, 2, 3), keepdims=True)
        var_gradient = -0.5 * np.power(self.var + self.eps, -1.5) * sum_

        # bhw stands for batch_size * height * width. Will be renamed to num_elems
        bhw = np.prod(self.input_.shape)/self.n_channels

        std_inv = 1.0 / np.sqrt(self.var + self.eps)

        mean_gradient = - std_inv * np.sum(norm_input_gradient, axis = (0, 2, 3), keepdims=True) + \
            var_gradient * -2 * np.mean(self.input_ - self.mean, axis = (0, 2, 3), keepdims=True)
        
        input_gradient = norm_input_gradient / np.sqrt(self.var + self.eps) + \
            var_gradient * 2 * (self.input_ - self.mean) / bhw + \
            mean_gradient / bhw

        return input_gradient
    
    # def backward(self, output_gradient: np.ndarray) -> np.ndarray:
    #     B = np.prod(self.input_.shape)/self.n_channels
        
    #     dL_dxi_hat = output_gradient * self.gamma
    #     dL_dvar = np.sum((-0.5 * dL_dxi_hat * (self.input_ - self.mean)), axis = (0, 2, 3), keepdims=True)  * ((self.var + self.eps) ** -1.5) # edit
    #     dL_davg = np.sum(-1.0 / np.sqrt(self.var + self.eps) * dL_dxi_hat, axis = (0, 2, 3), keepdims=True) + np.sum(dL_dvar * -2.0 * (self.input_ - self.mean), axis = (0, 2, 3), keepdims=True) / B #edit
        
    #     dL_dxi = (dL_dxi_hat / np.sqrt(self.var + self.eps)) + (2.0 * dL_dvar * (self.input_ -self.mean) / B) + (dL_davg / B) # dL_dxi_hat / sqrt()
    #     self.gamma_gradient = np.sum(output_gradient * self.norm_input, axis = (0, 2, 3), keepdims=True) # edit
    #     self.beta_gradient = np.sum(output_gradient, axis = (0, 2, 3), keepdims=True)
    #     return dL_dxi
        
    def get_parameters_and_gradients_and_ids(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        gamma_id = f'g{self.id}'
        beta_id = f'b{self.id}'
        parameters_and_gradients_and_ids = [
            (self.gamma, self.gamma_gradient, gamma_id),
            (self.beta, self.beta_gradient, beta_id)]
        return parameters_and_gradients_and_ids
    

class Flatten(Module):
    def forward(self, input_: np.ndarray) -> np.ndarray:
        self.input_shape = input_.shape
        batch_size = input_.shape[0]
        return input_.reshape(batch_size, -1)
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        return output_gradient.reshape(self.input_shape)


class ActivationLayer(Module):
    """
    This base class is not crucial but it presevrves OOP ideology and 
    it is useful for type hinting like List[ActivationLayer].
    """
    def __init__(self):
        pass

class ReLULayer(ActivationLayer):
    def forward(self, input_: np.ndarray) -> np.ndarray:
        self.input_ = input_
        return np.maximum(0, input_)
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        return output_gradient * (self.input_ > 0)

class SigmoidLayer(ActivationLayer):
    def forward(self, input_: np.ndarray) -> np.ndarray:
        # clip is used to avoid overflow
        # self.output = 1 / (1 + np.exp(-np.clip(input_, 1e-8, 1e4)))
        self.output = 1 / (1 + np.exp(-input_))
        return self.output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        return output_gradient * self.output * (1 - self.output)

class LinearActivation(ActivationLayer):
    def forward(self, input_: np.ndarray) -> np.ndarray:
        return input_
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        return output_gradient


def softmax(x: np.ndarray) -> np.ndarray:
    # The output of softmax will be same if we substract some constant c
    # from the input. It's same as multiplying initial expression by
    # e^(-c)/e^(-c). The substraction helps to avoid overflow.
    e_subtracted = np.exp(x - np.max(x, axis=1, keepdims=True)) 
    return e_subtracted / np.sum(e_subtracted, axis=1, keepdims=True)

class SoftMaxLayer(Module):
    def forward(self, input_: np.ndarray) -> np.ndarray:
        self.output = softmax(input_)
        return self.output
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        return output_gradient * self.output * (1 - self.output)
    
               

class CrossEntropyLoss:
    def forward(self, pred: np.ndarray, target: np.ndarray) -> float:
        self.pred = pred
        self.target = target
        batch_size = pred.shape[0]
        # summing over the batch and then dividing by the batch size
        # return -np.sum(np.dot(self.target, np.log(self.cliped_pred()).T)) / batch_size
        return -np.sum(self.target * np.log(self.cliped_pred())) / batch_size
    
    def backward(self) -> np.ndarray:
        batch_size = self.pred.shape[0]
        return - self.target / self.cliped_pred() / batch_size

    def cliped_pred(self) -> np.ndarray:
        # Clip is used to avoid negative values as input to if we don't
        # use softmax. !Maybe it's better to have an upper bound of 1 so that
        # the possible values of the input to log are in the range [1e-8, 1]
        # even if we don't use softmax
        return np.clip(self.pred, 1e-8, None)

class CrossEntropyLossWithSoftMax:
    def forward(self, activation: np.ndarray, target: np.ndarray) -> float:
        self.pred = np.clip(softmax(activation), 1e-8, None)
        self.target = target
        batch_size = activation.shape[0]
        return -np.sum(self.target * np.log(self.pred)) / batch_size
    
    def backward(self) -> np.ndarray:
        batch_size = self.pred.shape[0]
        return (self.pred - self.target) / batch_size


class Optimizer:
    def __init__(self, trainable_layers: List[TrainableLayer], learning_rate: float):
        self.learning_rate = learning_rate
        self.trainable_layers = trainable_layers
    
    def step(self):
        raise NotImplementedError

class AdamOptimizer(Optimizer):
    """
    I store m and v values for each weight gradient and bias gradient
    in dictionaries m and v where the key is the id of the parameter matrix
    which has the form "dW{layer_id}" or "db{layer_id}". Thus, the parameter
    matrix ids serve as gradient matrix ids.
    
    This solution works but I'm not sure that this approach could be used in a graph based computation. 

    There's also an ugly option to have an instance of AdamOptimizer for each parameter.
    """
    def __init__(self, trainable_layers: List[TrainableLayer], learning_rate: float = 0.001,
                 beta1: float = 0.9, beta2: float = 0.999, epsilon: float = 1e-8):
        #!? maybe we should pass paramters and parameters' ids to the optimizer instead of passing layers
        self.trainable_layers = trainable_layers
        self.learning_rate = learning_rate
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.m = {}
        self.v = {}
        self.t = 0
        for layer in self.trainable_layers:
            for param, _, id in layer.get_parameters_and_gradients_and_ids():
                # The params are used as shape source because they have 
                # the same shape as the gradients and are garanteed 
                # to be initialized.
                self.m[id] = np.zeros_like(param)
                self.v[id] = np.zeros_like(param)
    
    def update(self, gradient: np.ndarray, cache_id: str) -> None:
        self.m[cache_id] = self.beta1 * self.m[cache_id] + (1 - self.beta1) * gradient
        self.v[cache_id] = self.beta2 * self.v[cache_id] + (1 - self.beta2) * gradient ** 2
        
    def step(self) -> None:
        self.t += 1
        for layer in self.trainable_layers:
            #! Since np arrays are passed by reference the weights and bias
            # layer properties are going to be properly updated.
            for parameter, gradient, cache_id in layer.get_parameters_and_gradients_and_ids():
                self.update(gradient, cache_id)
                m_corrected = self.m * (1 - self.beta1 ** self.t)
                v_corrected = self.v * (1 - self.beta2 ** self.t)
                parameter -= self.learning_rate * m_corrected / (np.sqrt(v_corrected) + self.epsilon)


class GradientDescentOptimizer(Optimizer):
    def __init__(self, trainable_layers: List[Module], learning_rate: float = 0.001):
        self.trainable_layers = trainable_layers
        self.learning_rate = learning_rate

    def step(self) -> None:
        for layer in self.trainable_layers:
            #! Since np arrays are passed by reference the weights and bias
            # layer properties are going to be properly updated.
            for parameter, gradient, _ in layer.get_parameters_and_gradients_and_ids():
                parameter -= self.learning_rate * gradient


class Sequential(Module):
    """
    A stack of sequentially connected neural network modules. 
    Attributes:
        nn_modules: a list of neural network modules that are going to be
            connected sequentially.
    """
    def __init__(self, nn_modules: List):
        self.trainable_layers = []
        self.nn_modules = nn_modules

        self.trainable_layers = []
        for nn_module in self.nn_modules:
            self.trainable_layers.extend(nn_module.get_trainable_layers())

    def forward(self, input_: np.ndarray) -> np.ndarray:
        for nn_module in self.nn_modules:
            input_ = nn_module.forward(input_)
        return input_
    
    def backward(self, output_gradient: np.ndarray) -> np.ndarray:
        for nn_module in reversed(self.nn_modules):
            output_gradient = nn_module.backward(output_gradient)
        return output_gradient
    
    def get_trainable_layers(self) -> List[TrainableLayer]:
        return self.trainable_layers
    