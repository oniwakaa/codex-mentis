import pytest
import os
import matplotlib
# Set matplotlib backend to Agg to prevent headless environment errors
matplotlib.use('Agg')
from codex_mentis.math_engine.plots import MathPlotter

def test_plot_function(tmp_path):
    plotter = MathPlotter()
    
    # Plot basic function
    plotter.plot_function("x**2", (-2.0, 2.0), "Quadratic function")
    
    # Save plot to temp file
    save_file = str(tmp_path / "plot_fn.png")
    plotter.save_plot(save_file)
    assert os.path.exists(save_file)

def test_plot_parametric(tmp_path):
    plotter = MathPlotter()
    
    # Parametric circle
    plotter.plot_parametric("cos(t)", "sin(t)", (0.0, 6.28), "Circle")
    
    save_file = str(tmp_path / "plot_param.png")
    plotter.save_plot(save_file)
    assert os.path.exists(save_file)

def test_plot_vector_field(tmp_path):
    plotter = MathPlotter()
    
    # Rotational flow
    plotter.plot_vector_field("-y", "x", (-5.0, 5.0), (-5.0, 5.0), "Vortex")
    
    save_file = str(tmp_path / "plot_vector.png")
    plotter.save_plot(save_file)
    assert os.path.exists(save_file)

def test_plot_surface(tmp_path):
    plotter = MathPlotter()
    
    # Paraboloid surface
    plotter.plot_surface("x**2 + y**2", (-2.0, 2.0), (-2.0, 2.0), "Paraboloid")
    
    save_file = str(tmp_path / "plot_surface.png")
    plotter.save_plot(save_file)
    assert os.path.exists(save_file)

def test_plot_scatter(tmp_path):
    plotter = MathPlotter()
    
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.0, 4.0, 9.0, 16.0]
    plotter.plot_scatter(x, y, "Scatter Data")
    
    save_file = str(tmp_path / "plot_scatter.png")
    plotter.save_plot(save_file)
    assert os.path.exists(save_file)
