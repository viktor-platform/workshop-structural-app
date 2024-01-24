from viktor import ViktorController
from viktor.parametrization import ViktorParametrization, NumberField
from viktor.views import ImageView, ImageResult

import matplotlib.pyplot as plt
from io import StringIO
from anastruct import SystemElements


class Parametrization(ViktorParametrization):
    height = NumberField('Height', min=1, max=30, default=5)
    length = NumberField('Length', min=1, max=30, default=5)

    magnitude = NumberField('Magnitude', min=1, max=30, default=5)



class Controller(ViktorController):
    label = 'My Entity Type'
    parametrization = Parametrization
    
    @staticmethod
    def make_analysis(params):
        ss = SystemElements()
        ss.add_element(location=[[0,0], [0, params.height]])
        ss.add_element(location=[[0,params.height], [params.length, params.height]])
        ss.add_element(location=[[params.length, params.height], [params.length, 0]])

        ss.add_support_fixed(node_id=1)
        ss.add_support_fixed(node_id=4)

        ss.q_load(q=-params.magnitude, element_id=2, direction='element')
        ss.solve()

        return ss
    

    @ImageView("Structures & Forces", duration_guess=1)
    def create_structure(self, params, **kwargs):
        ss = self.make_analysis(params)
        fig = ss.show_structure(show=False, )
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)


    @ImageView("Bending Moment", duration_guess=1)
    def create_bending(self, params, **kwargs):
        ss = self.make_analysis(params)
        fig = ss.show_bending_moment(show=False)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)
    

    @ImageView("Shear Stresses", duration_guess=1)
    def create_shear(self, params, **kwargs):
        ss = self.make_analysis(params)
        fig = ss.show_shear_force(show=False)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)
    
    @ImageView("Deformation", duration_guess=1)
    def create_deformation(self, params, **kwargs):
        ss = self.make_analysis(params)
        fig = ss.show_displacement(show=False)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)
