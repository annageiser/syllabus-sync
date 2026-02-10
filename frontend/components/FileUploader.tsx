import React, { useCallback } from 'react';

interface FileUploaderProps {
    onFileUpload: (file: File) => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({ onFileUpload }) => {
    const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            onFileUpload(e.dataTransfer.files[0]);
        }
    }, [onFileUpload]);

    const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            onFileUpload(e.target.files[0]);
        }
    };

    return (
        <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center hover:bg-gray-50 transition-colors cursor-pointer"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
        >
            <input
                type="file"
                className="hidden"
                id="file-upload"
                onChange={handleChange}
                accept=".pdf,.xlsx,.xls,.docx,.html,.htm"
            />
            <label htmlFor="file-upload" className="cursor-pointer block">
                <div className="text-4xl mb-4">📄</div>
                <h3 className="text-lg font-semibold mb-2">Drag & Drop your schedule here</h3>
                <p className="text-gray-500 text-sm">Supports PDF, Excel, Word, HTML</p>
                <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition">
                    Browse Files
                </button>
            </label>
        </div>
    );
};

export default FileUploader;
