import setuptools

setuptools.setup(
    name="hegic_analytics",
    version="0.0.1",
    packages=setuptools.find_packages(),
    install_requires=[
        "pandas==1.1.4",
        "requests==2.25.0",
        "jupyter==1.0.0",
        "dash==1.17.0",
    ],
)
