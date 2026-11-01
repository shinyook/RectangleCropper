import setuptools

install_requires = [
    'Pillow>=10.0,<13',
    'numpy>=1.23.5,<3',
    'scipy>=1.10,<2',
]
setuptools.setup(
    name="rectcropper",
    version="1.2.0",
    license='MIT',
    author="Shinyook Lee",
    author_email="tlsdbr97@gmail.com",
    description="Crop image to rectangle",
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url="https://github.com/shinyook/rectcropper",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    entry_points={'console_scripts': ['rectcropper=rectcropper.__main__:main']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.9',
)