import os
import cv2
from accessify import private

from openvino.inference_engine import IENetwork, IECore


class Detector(object):
    def __init__(self, ie, path_to_model_xml, path_to_lib, label_class, scale=None, thr=0.3, device='CPU'):
        self.OUTPUT_SIZE = 7
        self.model = IENetwork(model=path_to_model_xml, weights=os.path.splitext(path_to_model_xml)[0] + '.bin')
        self._input_layer_name = next(iter(self.model.inputs))
        self._output_layer_name = next(iter(self.model.outputs))

        assert len(self.model.outputs) == 1, "Expected 1 output blob"

        assert len(self.model.outputs[self._output_layer_name].shape) == 4 and \
               self.model.outputs[self._output_layer_name].shape[3] == self.OUTPUT_SIZE, \
            "Expected model output shape with %s outputs" % (self.OUTPUT_SIZE)

        self._ie = ie
        if device == 'CPU':
            self._ie.add_extension(path_to_lib, device)
        self._exec_model = self._ie.load_network(self.model, device)
        self._scale = scale
        self._thr = thr
        self._label_class = label_class
        _, _, self.input_h,  self.input_w = self.model.inputs[self._input_layer_name].shape
        self._h = -1
        self._w = -1
        self.infer_time = -1

    @private
    def preprocess(self, img):
        self._h, self._w, _ = img.shape
        if self._h != self.input_h or self._w != self.input_w:
            img = cv2.resize(img, dsize=(self.input_w, self.input_h), fy=self._h / self.input_h,
                             fx=self._h / self.input_h)
        img = img.transpose(2, 0, 1)
        return img[None, ]

    @private
    def infer(self, prep_img):
        t0 = cv2.getTickCount()
        output = self._exec_model.infer(inputs={self._input_layer_name: prep_img})
        self.infer_time = (cv2.getTickCount() - t0) / cv2.getTickFrequency()
        return output

    @private
    def postprocess(self, bboxes):

        def coord_translation(bbox):
            xmin = int(self._w * bbox[0])
            ymin = int(self._h * bbox[1])
            xmax = int(self._w * bbox[2])
            ymax = int(self._h * bbox[3])
            w_box = xmax - xmin
            h_box = ymax - ymin
            return [xmin, ymin, w_box, h_box]

        bboxes_new = [coord_translation(bbox[3:]) for bbox in bboxes if bbox[1] == self._label_class and bbox[2] > self._thr]

        return bboxes_new

    def detect(self, img):
        img = self.preprocess(img)
        output = self.infer(img)
        bboxes = self.postprocess(output[self._output_layer_name][0][0])
        return bboxes
