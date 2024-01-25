import os
from tempfile import NamedTemporaryFile
import matplotlib.pyplot as plt
from io import StringIO, BytesIO
from anastruct import SystemElements
from pathlib import Path

from viktor import ViktorController, progress_message, UserError
from viktor.parametrization import ViktorParametrization, NumberField, Step, TextField, DateField, FileField, SetParamsButton, Section, Text, OptionField
from viktor.views import ImageView, ImageResult, PDFResult, PDFView
from viktor.external.spreadsheet import SpreadsheetCalculationInput, SpreadsheetCalculation
from viktor.external.word import WordFileTag, render_word_file, WordFileImage
from viktor.result import SetParamsResult
from viktor.utils import convert_word_to_pdf



class Parametrization(ViktorParametrization):
    geometry = Step("geometry", views=["create_structure"])
    
    geometry.structure = Section("Structure")
    geometry.structure.text = Text("""
## Structure design
In this section you may adjust the dimensions of the portal frame.
You can also upload the excel sheet for the MoI calculations in tube design.
                         """)
    
    geometry.structure.height = NumberField('Height', min=10, max=3000, default=500, suffix="mm")
    geometry.structure.length = NumberField('Length', min=10, max=3000, default=500, suffix="mm")

    geometry.tube = Section('Tube design')
    geometry.tube.excel_file = FileField("Upload Excel file", file_types=[".xlsx"], flex=100)

    geometry.tube.tube_width = NumberField("width of tube", min=10, max=50, default=20, suffix="mm")
    geometry.tube.tube_height = NumberField("height of tube", min=10, max=50, default=20, suffix="mm")
    geometry.tube.tube_thickness = NumberField("thickness of tube", min=1, max=10, default=5, suffix="mm")

    geometry.tube.emodulus = NumberField("E-Modules", min=30000, max=210000, default=70000, suffix="N/mm^2")

    geometry.tube.moment_of_inertia = NumberField("Moment of Inertia", suffix=('mm^4'), num_decimals=2)

    geometry.tube.fill_moment_of_inertia = SetParamsButton("Calculate Moment of Inertia", method="calculate_moment_of_inertia")

    forces = Step("Forces", views=['create_forces'])
    forces.text = Text("""
## Loading of the structure
In this section you may adjust the magnitude of the distributed load.
You may also choose an element to place the load on.
                         """)
    
    forces.magnitude = NumberField('Magnitude', min=1, max=30, default=5, suffix="N/mm")
    forces.element = OptionField('Choose an element to place the force on', options=[1,2,3], default=2, flex=60)

    analysis = Step("Analysis", views=['create_bending', 'create_shear', 'create_displacement'])

    reporting = Step("Report", views=['create_report'])
    reporting.text = Text("""
## Reporting
An important part of engineering is reporting.
Give your project a name, a date and feel free to download your design and results.                         
                         """)
    
    reporting.project_name = TextField('Project Title: ')
    reporting.project_date = DateField("Design date:")


class Controller(ViktorController):
    label = 'My Entity Type'
    parametrization = Parametrization

    @staticmethod
    def calculate_moment_of_inertia(params, **kwargs):
        if not params.geometry.tube.excel_file:
            raise UserError("Please first upload an excel file which calculates the moment of inertia")

        excel_file_temp = NamedTemporaryFile(delete=False, suffix=".xlsx")
        excel_file_temp.write(params.geometry.tube.excel_file.file.getvalue_binary())
        excel_file_temp.close()

        inputs = []
        inputs.append(SpreadsheetCalculationInput("width", params.geometry.tube.tube_width))
        inputs.append(SpreadsheetCalculationInput("height", params.geometry.tube.tube_height))
        inputs.append(SpreadsheetCalculationInput("thickness", params.geometry.tube.tube_thickness))
        spreadsheet = SpreadsheetCalculation.from_path(excel_file_temp.name, inputs)
        result = spreadsheet.evaluate(include_filled_file=True)
        values = result.values

        moment_of_inertia = values['moment_of_inertia']
        os.unlink(excel_file_temp.name)
        print(moment_of_inertia)
        return SetParamsResult({"geometry":{"tube": {"moment_of_inertia": float(moment_of_inertia)}}})

    
    @staticmethod
    def make_analysis(params):
        height = params.geometry.structure.height
        length = params.geometry.structure.length
        if not params.geometry.tube.excel_file:
            se = SystemElements()
        else:
            emod_inertia = params.geometry.tube.emodulus * params.geometry.tube.moment_of_inertia
            emod_area = params.geometry.tube.emodulus * params.geometry.tube.tube_height * params.geometry.tube.tube_thickness 
            se = SystemElements(EA=emod_area, EI=emod_inertia)

        se.add_element(location=[[0,0], [0, height]])
        se.add_element(location=[[0,height], [length, height]])
        se.add_element(location=[[length, height], [length, 0]])

        se.add_support_fixed(node_id=1)
        se.add_support_fixed(node_id=4)

        return se
    

    @ImageView("Structure", duration_guess=1)
    def create_structure(self, params, **kwargs):
        se = self.make_analysis(params)
        fig = se.show_structure(show=False, annotations=True)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)

    @ImageView("Forces", duration_guess=1)
    def create_forces(self, params, **kwargs):
        se = self.make_analysis(params)
        se.q_load(q=-params.forces.magnitude, element_id=params.forces.element, direction='element')
        se.solve()
        fig = se.show_structure(show=False, annotations=True)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)

    @ImageView("Bending Stress", duration_guess=1)
    def create_bending(self, params, **kwargs):
        se = self.make_analysis(params)
        se.q_load(q=-params.forces.magnitude, element_id=params.forces.element, direction='element')
        se.solve()
        fig = se.show_bending_moment(show=False)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)
    

    @ImageView("Shear Stress", duration_guess=1)
    def create_shear(self, params, **kwargs):
        #add your code here:

        return ImageResult()
    
    @ImageView("Displacement", duration_guess=1)
    def create_displacement(self, params, **kwargs):
        #Add your code here:

        return ImageResult()

    @PDFView("Report", duration_guess=10)
    def create_report(self, params, **kwargs):
        se = self.make_analysis(params)
        se.q_load(q=-params.forces.magnitude, element_id=params.forces.element, direction='element')
        se.solve()

        components = []

        fig = se.show_structure(show=False, annotations=True)
        structure_image = BytesIO()
        fig.savefig(structure_image, format='png')

        fig = se.show_bending_moment(show=False)
        bending_stress_image = BytesIO()
        fig.savefig(bending_stress_image, format='png')

        fig = se.show_shear_force(show=False)
        shear_stress_image = BytesIO()
        fig.savefig(shear_stress_image, format='png')

        fig = se.show_displacement(show=False)
        displacement_image = BytesIO()
        fig.savefig(displacement_image, format='png')
        

        
        progress_message(message="Preparing data and images...")

        data = {
            "project_name": params.reporting.project_name,
            "project_date": str(params.reporting.project_date),
        }

        images = {
            "structure_image": structure_image,
            "shear_stress_image": shear_stress_image,
            "displacement_image": displacement_image,
            "bend_stress_image": bending_stress_image,
        }

        # make tags
        for tag, value in data.items():
            components.append(WordFileTag(tag, value))
        for key, image in images.items():
            components.append(WordFileImage(image, key, width=432))

        # Get path to template and render word file
        template_path = Path(__file__).parent / "report_template.docx"
        with open(template_path, 'rb') as template:
            word_file = render_word_file(template, components)
            pdf_file = convert_word_to_pdf(word_file.open_binary())

        progress_message(message="Rendering the report...")

        return PDFResult(file=pdf_file)